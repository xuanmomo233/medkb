"""Proof-based archival of full catalog inputs; never infer consumption from age."""
from __future__ import annotations

import gzip
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def locked_payload(path: Path):
    """Windows readers remain allowed; writes are denied until verification/deletion ends."""
    if os.name != "nt":
        with path.open("rb") as stream:
            yield stream
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000, 0x1 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, "rb") as stream:
        yield stream


def item_digest(item: dict) -> str:
    return digest(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def artifact_bytes(path: Path) -> bytes:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as f:
            return f.read()
    if path.is_file():
        return path.read_bytes()
    with gzip.open(path.with_suffix(path.suffix + ".gz"), "rb") as f:
        return f.read()


def safe_path(root: Path, value: str, *, payload: bool = False) -> Path:
    root = root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    # Check lexical containment first, then reject links/junctions in every component.
    if ".." in path.parts:
        raise ValueError("Parent traversal in artifact path")
    relative = path.relative_to(root)
    if not relative.parts or relative.parts[0] not in (["work"] if payload else ["work", "docs"]):
        raise ValueError("Artifact is outside the allowed workspace roots")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Linked artifact paths are not eligible for cleanup")
    if path.resolve() != path:
        raise ValueError("Artifact resolves outside its declared path")
    return path


def read_json(path: Path) -> dict:
    value = json.loads(artifact_bytes(path).decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected an artifact object")
    return value


def verified_publication(receipt: dict) -> bool:
    sha = receipt.get("prepared_catalog_sha256")
    deployment = receipt.get("deployment", {})
    post = receipt.get("online_postread", {})
    return bool(sha and receipt.get("local_catalog_sync_performed") is True
                and receipt.get("production_write_performed") is True
                and receipt.get("local_synced_sha256") == sha
                and deployment.get("deployed") is True
                and deployment.get("health_passed") is True
                and deployment.get("rolled_back") is not True
                and deployment.get("catalog_sha256") == sha
                and post.get("catalog_sha256") == sha
                and post.get("container_running") is True
                and post.get("health", {}).get("status") == 200)


def declared_sources(*documents: dict) -> list[str]:
    refs = set()
    for doc in documents:
        for key in ("source_prepare_receipts", "source_deltas", "source_delta_paths"):
            for row in doc.get(key, []) or []:
                value = row if isinstance(row, str) else next(
                    (row[k] for k in ("source_delta", "delta_path", "prepare_receipt")
                     if isinstance(row, dict) and isinstance(row.get(k), str)), None)
                if value and value.endswith(".json"):
                    refs.add(value)
    return sorted(refs)


def published_receipts(root: Path):
    for path in (root / "work").rglob("publish-receipt-*.json"):
        try:
            safe_path(root, str(path))
            receipt = read_json(path)
            if verified_publication(receipt):
                yield path, receipt
        except (OSError, ValueError):
            continue


def pending_reference_dirs(root: Path) -> set[Path]:
    """Protect inputs also referenced by an unfinished aggregate, including old drafts."""
    published = {r["prepared_catalog_sha256"] for _, r in published_receipts(root)}
    protected = set()
    for path in (root / "work").rglob("manifest*.json"):
        try:
            safe_path(root, str(path))
            doc = read_json(path)
            if doc.get("prepared_catalog_sha256") in published:
                continue
            for ref in declared_sources(doc):
                protected.add(safe_path(root, ref).parent)
        except (OSError, ValueError):
            continue
    return protected


def candidate_inputs(root: Path, receipt_path: Path, plan: dict, delta: dict,
                     prepared_raw: bytes, *, protected_dirs=(), min_age_seconds=0,
                     max_candidates: int | None = None) -> dict:
    receipt_path = safe_path(root, str(receipt_path))
    receipt = read_json(receipt_path)
    expected = receipt.get("prepared_catalog_sha256")
    if not verified_publication(receipt) or digest(prepared_raw) != expected:
        raise ValueError("Publication is not independently verified and locally synchronized")
    if plan.get("prepared_catalog_sha256") != expected or delta.get("prepared_catalog_sha256") != expected:
        raise ValueError("Publication plan/delta do not match the verified catalog")
    catalog = json.loads(prepared_raw)
    parent_items = {i["id"]: item_digest(i) for i in catalog["items"]}
    entries = delta.get("entries", [])
    parent_changes = {e["item_id"]: e["prepared_item_sha256"] for e in entries}
    if len(parent_changes) != len(entries) or set(parent_changes) != set(receipt.get("changed_item_ids", [])):
        raise ValueError("Publication allowlist does not match the receipt")
    if set(parent_changes) != set(plan.get("changed_item_ids", [])):
        raise ValueError("Publication plan allowlist changed")
    if any(parent_items.get(i) != sha for i, sha in parent_changes.items()):
        raise ValueError("Publication delta differs from the archived catalog")
    result = {"publication_receipt": str(receipt_path.relative_to(root)),
              "publication_receipt_sha256": digest(receipt_path.read_bytes()), "candidates": [], "skipped": []}
    protected = [Path(p).resolve() for p in protected_dirs]
    seen = set()
    for ref in declared_sources(plan, delta):
        if max_candidates is not None and len(result["candidates"]) >= max_candidates:
            result["skipped"].append({"source": ref, "reason": "Global candidate limit reached; remaining inputs not scanned"})
            break
        try:
            source = safe_path(root, ref)
            if any(source == p or p in source.parents for p in protected):
                raise ValueError("Referenced by an active or unfinished consumer")
            # A source delta is usable only with a matching successful prepare receipt.
            receipts = [source] if source.name.startswith("prepare-receipt") else sorted(source.parent.glob("prepare-receipt*.json"))
            if not receipts:
                raise ValueError("No exact prepare receipt for the declared source")
            matched = False
            for child_receipt_path in receipts:
                child = read_json(safe_path(root, str(child_receipt_path)))
                if child.get("mode") != "prepare-only" or child.get("exact_allowlist_valid") is not True or child.get("production_write_performed") is not False:
                    continue
                child_sha = child.get("prepared_catalog_sha256")
                ids = set(child.get("changed_item_ids", []))
                if not ids or child.get("changed_item_count") != len(ids) or not ids.issubset(parent_changes):
                    continue
                delta_paths = [source] if not source.name.startswith("prepare-receipt") else sorted(source.parent.glob("combined-delta*.json"))
                child_deltas = []
                for dp in delta_paths:
                    cd = read_json(safe_path(root, str(dp)))
                    if cd.get("prepared_catalog_sha256") == child_sha and cd.get("baseline_catalog_sha256") == child.get("baseline_catalog_sha256"):
                        child_deltas.append((dp, cd))
                if len(child_deltas) != 1:
                    continue
                dp, cd = child_deltas[0]
                ce = cd.get("entries", [])
                if len(ce) != len(ids) or {e.get("item_id") for e in ce} != ids:
                    continue
                if any(e.get("operation") not in ("add", "update")
                       or parent_changes.get(e["item_id"]) != e.get("prepared_item_sha256")
                       or item_digest(e.get("prepared_item", {})) != e.get("prepared_item_sha256") for e in ce):
                    continue
                paths = sorted(source.parent.glob("prepared-catalog*.json"))
                for path in paths:
                    if max_candidates is not None and len(result["candidates"]) >= max_candidates:
                        result["skipped"].append({"source": ref, "reason": "Global candidate limit reached; remaining inputs not scanned"})
                        break
                    path = safe_path(root, str(path), payload=True)
                    if path in seen or not path.is_file():
                        continue
                    stat = path.stat()
                    if time.time() - stat.st_mtime < min_age_seconds:
                        result["skipped"].append({"path": str(path.relative_to(root)), "reason": "Recently changed; preserve for in-flight audit"})
                        continue
                    raw = path.read_bytes()
                    if digest(raw) != child_sha:
                        continue
                    child_items = {i["id"]: item_digest(i) for i in json.loads(raw)["items"] if i["id"] in ids}
                    if any(child_items.get(i) != parent_changes[i] for i in ids):
                        continue
                    result["candidates"].append({"path": str(path.relative_to(root)), "sha256": child_sha,
                        "bytes": len(raw), "mtime_ns": stat.st_mtime_ns,
                        "prepare_receipt": str(child_receipt_path.relative_to(root)),
                        "prepare_receipt_sha256": digest(child_receipt_path.read_bytes()),
                        "source_delta": str(dp.relative_to(root)), "source_delta_sha256": digest(dp.read_bytes()),
                        "consumed_item_ids": sorted(ids)})
                    seen.add(path)
                    matched = True
            if not matched:
                result["skipped"].append({"source": ref, "reason": "No unique unchanged full input with fully consumed items"})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["skipped"].append({"source": ref, "reason": str(exc)})
    return result


def _archive_payload_locked(path: Path, expected: bytes) -> Path:
    """Write and verify the gzip atomically before removing an unchanged original."""
    archived = path.with_suffix(path.suffix + ".gz")
    if archived.is_symlink() or (hasattr(archived, "is_junction") and archived.is_junction()):
        raise ValueError("Linked archive is not eligible; original retained")
    before = path.stat() if path.exists() else None
    if before and path.read_bytes() != expected:
        raise ValueError("Completed payload changed; original retained")
    if not archived.exists():
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".catalog-archive-", delete=False) as f:
            temp = Path(f.name)
        try:
            with gzip.open(temp, "wb", compresslevel=1) as f:
                f.write(expected)
            with gzip.open(temp, "rb") as f:
                if f.read() != expected:
                    raise ValueError("Compressed payload verification failed")
            # Never replace an archive written by another publisher/cleaner.
            if archived.exists():
                pass
            else:
                try:
                    os.link(temp, archived)
                except FileExistsError:
                    pass
        finally:
            temp.unlink(missing_ok=True)
    with gzip.open(archived, "rb") as f:
        if f.read() != expected:
            raise ValueError("Compressed payload verification failed; original retained")
    if path.exists():
        after = path.stat()
        if before is None or (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino) or path.read_bytes() != expected:
            raise ValueError("Payload changed during archival; original retained")
        path.unlink()
    return archived


def archive_payload(path: Path, expected: bytes) -> Path:
    if not path.exists():
        return _archive_payload_locked(path, expected)
    with locked_payload(path):
        return _archive_payload_locked(path, expected)


def archive_consumed(root: Path, plan: dict, *, apply=False) -> dict:
    """Recheck evidence and content immediately before applying a recorded plan."""
    root = root.resolve()
    receipt = safe_path(root, plan["publication_receipt"])
    if (plan.get("publication_receipt_sha256") != digest(receipt.read_bytes())
            or not verified_publication(read_json(receipt))):
        raise ValueError("Publication receipt is no longer verified")
    result = {"archived": [], "skipped": list(plan.get("skipped", []))}
    # A plan is a snapshot, not a durable authorization. Recompute active references
    # at apply time so a newly started aggregate protects its source input.
    protected = pending_reference_dirs(root) if apply else set()
    for row in plan["candidates"]:
        try:
            path = safe_path(root, row["path"], payload=True)
            if any(path == directory or directory in path.parents for directory in protected):
                raise ValueError("Referenced by an active or unfinished consumer; original retained")
            for key, hash_key in [("prepare_receipt", "prepare_receipt_sha256"), ("source_delta", "source_delta_sha256")]:
                if digest(safe_path(root, row[key]).read_bytes()) != row[hash_key]:
                    raise ValueError("Consumption evidence changed; original retained")
            stat = path.stat()
            if stat.st_size != row["bytes"] or stat.st_mtime_ns != row["mtime_ns"]:
                raise ValueError("Candidate changed after inventory; original retained")
            raw = path.read_bytes()
            if digest(raw) != row["sha256"]:
                raise ValueError("Candidate hash changed; original retained")
            if not apply:
                continue
            archived = archive_payload(path, raw)
            result["archived"].append({**row, "archive": str(archived.relative_to(root)), "archive_bytes": archived.stat().st_size})
        except (OSError, ValueError) as exc:
            result["skipped"].append({"path": row["path"], "reason": str(exc)})
    return result


def historical_context(root: Path, receipt_path: Path):
    receipt = read_json(receipt_path)
    paths = receipt.get("artifact_paths", {})
    if paths and all(k in paths for k in ("manifest", "delta", "prepared")):
        return (read_json(safe_path(root, paths["manifest"])), read_json(safe_path(root, paths["delta"])),
                artifact_bytes(safe_path(root, paths["prepared"])))
    directories = [receipt_path.parent]
    for key in ("prepared_archive_path",):
        if receipt.get(key):
            directories.append(safe_path(root, receipt[key]).parent)
    for directory in dict.fromkeys(directories):
        plans = [p for p in directory.glob("manifest*.json") if read_json(p).get("prepared_catalog_sha256") == receipt.get("prepared_catalog_sha256")]
        deltas = [p for p in directory.glob("combined-delta*.json") if read_json(p).get("prepared_catalog_sha256") == receipt.get("prepared_catalog_sha256")]
        if len(plans) != 1 or len(deltas) != 1:
            continue
        path = safe_path(root, receipt["prepared_archive_path"]) if receipt.get("prepared_archive_path") else directory / "prepared-catalog.json"
        raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else artifact_bytes(path)
        return read_json(plans[0]), read_json(deltas[0]), raw
    raise ValueError("No unique publication manifest/delta/catalog context")
