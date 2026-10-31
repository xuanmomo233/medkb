"""Validate/repair evidence references by full item identity, never by filename prefix."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
from collections import deque


def read_bytes(path: Path) -> bytes:
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes())
    return path.read_bytes()


def read_json(path: Path):
    return json.loads(read_bytes(path).decode("utf-8-sig"))


def evidence_pack_filename(item_id: str) -> str:
    """Bound path length without truncating the identity used to derive the filename."""
    return "item-" + hashlib.sha256(item_id.encode("utf-8")).hexdigest() + ".json"


def find_reconciliation_snapshot(folder: Path, root: Path, live_path: Path, wanted_sha: str) -> bytes:
    live = live_path.read_bytes()
    if hashlib.sha256(live).hexdigest() == wanted_sha:
        return live
    for receipt_path in folder.rglob("publish-receipt*.json"):
        try:
            receipt = read_json(receipt_path)
        except (OSError, ValueError):
            continue  # Another publisher may still be writing a new receipt.
        if receipt.get("prepared_catalog_sha256") != wanted_sha:
            continue
        for ref in [receipt.get("prepared_archive_path"), receipt.get("artifact_paths", {}).get("prepared")]:
            if not ref:
                continue
            path = root / ref
            path.resolve().relative_to(root.resolve())
            if not path.is_file():
                path = Path(str(path) + ".gz")
            if path.is_file():
                raw = read_bytes(path)
                if hashlib.sha256(raw).hexdigest() == wanted_sha:
                    return raw
    raise ValueError("Preserved reconciliation snapshot unavailable; do not substitute the live catalog")


def publication_chain(folder: Path, baseline_sha: str, wanted_sha: str) -> list[dict]:
    links = {}
    for path in sorted(folder.rglob("publish-receipt*.json")):
        try:
            receipt = read_json(path)
            prepared = receipt.get("prepared_catalog_sha256")
            post = receipt.get("online_postread", {})
            deployed = receipt.get("deployment", {})
            if not (prepared and receipt.get("production_write_performed") is True
                    and receipt.get("local_catalog_sync_performed") is True
                    and receipt.get("local_synced_sha256") == prepared
                    and deployed.get("deployed") is True and deployed.get("health_passed") is True
                    and deployed.get("rolled_back") is not True
                    and post.get("catalog_sha256") == prepared
                    and post.get("container_running") is True and post.get("health", {}).get("status") == 200):
                continue
            links.setdefault(receipt.get("baseline_catalog_sha256"), []).append(receipt)
        except (OSError, ValueError):
            continue
    queue = deque([(baseline_sha, [])])
    seen = {baseline_sha}
    while queue:
        state, chain = queue.popleft()
        if state == wanted_sha:
            return chain
        for receipt in links.get(state, []):
            following = receipt["prepared_catalog_sha256"]
            if following not in seen:
                seen.add(following)
                queue.append((following, chain + [receipt]))
    raise ValueError("No fully verified publication chain connects the frozen baseline to reconciliation snapshot")


def safe_reference(folder: Path, reference: str) -> Path:
    rel = Path(reference)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Evidence reference must remain relative to its audit directory")
    path = folder / rel
    path.resolve().relative_to(folder.resolve())
    for candidate in [path, *path.parents]:
        if candidate == folder:
            break
        if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
            raise ValueError("Linked evidence reference is not accepted")
    return path


def check_references(folder: Path, coverage: dict, *, repair=False) -> dict:
    folder = folder.resolve()
    expected_sha = coverage.get("catalog_baseline", {}).get("sha256")
    errors, repairs = [], []
    if not isinstance(expected_sha, str) or not expected_sha:
        errors.append({"reason": "Frozen coverage baseline SHA is required"})
    packs = {}
    batches = {}
    for path in sorted((folder / "gpt-adjudication").glob("*.json*")):
        if not (path.name.endswith(".json") or path.name.endswith(".json.gz")):
            continue
        try:
            safe_reference(folder, path.relative_to(folder).as_posix())
            pack = read_json(path)
            ident = pack.get("item_id")
            if not isinstance(ident, str) or not ident:
                raise ValueError("Evidence pack has no full item_id")
            packs.setdefault(ident, []).append((path, pack))
            if expected_sha and pack.get("catalog_sha256") != expected_sha:
                errors.append({"item_id": ident, "reason": "Evidence pack baseline SHA mismatch"})
        except (OSError, ValueError, TypeError) as exc:
            errors.append({"path": str(path), "reason": str(exc)})
    for ident, candidates in packs.items():
        if len(candidates) != 1:
            errors.append({"item_id": ident, "reason": "Duplicate evidence pack identity; no automatic choice"})
    for path in sorted((folder / "batches").glob("*.json*")):
        if not (path.name.endswith(".json") or path.name.endswith(".json.gz")):
            continue
        try:
            safe_reference(folder, path.relative_to(folder).as_posix())
            batch = read_json(path)
            for row in batch.get("items", []):
                ident = row.get("item_id")
                if ident in batches:
                    errors.append({"item_id": ident, "reason": "Duplicate batch item identity"})
                batches[ident] = (path, row)
        except (OSError, ValueError, TypeError) as exc:
            errors.append({"path": str(path), "reason": str(exc)})
    items = coverage.get("items", {})
    if not isinstance(items, dict):
        return {"errors": [{"reason": "coverage.items must be indexed by full item ID"}], "repairs": [], "pack_count": len(packs)}
    for ident in packs.keys() - items.keys():
        errors.append({"item_id": ident, "reason": "Evidence pack is outside coverage"})
    for ident, row in items.items():
        batch = batches.get(ident)
        if batch is None:
            errors.append({"item_id": ident, "reason": "No unique batch record"})
        elif row.get("batch_file") != batch[0].relative_to(folder).as_posix():
            errors.append({"item_id": ident, "reason": "batch_file does not identify the batch containing this item"})
        candidates = packs.get(ident, [])
        actual = None
        if len(candidates) == 1:
            path, pack = candidates[0]
            if not expected_sha or pack.get("catalog_sha256") == expected_sha:
                actual = path.relative_to(folder).as_posix()
        declared = row.get("evidence_pack")
        if declared:
            try:
                safe_reference(folder, declared)
            except (OSError, ValueError) as exc:
                errors.append({"item_id": ident, "reason": str(exc)})
                continue
        if actual is not None and declared != actual:
            correction = {"item_id": ident, "before": declared, "after": actual}
            repairs.append(correction)
            if repair:
                row["evidence_pack"] = actual
            else:
                errors.append({"item_id": ident, "reason": "Evidence reference differs from full-ID-matched pack", "actual": actual})
        elif declared and actual is None:
            errors.append({"item_id": ident, "reason": "Evidence reference has no unambiguous matching pack"})
        verdict = batch[1].get("conflict_verdict") if batch else None
        if verdict in ("true_conflict", "subset_scope_conflict") and actual is None:
            errors.append({"item_id": ident, "reason": "Conflict item has no identity/baseline-matched pack"})
        supplement = row.get("supplemental_evidence")
        if supplement:
            try:
                path = safe_reference(folder, supplement)
                if not path.is_file() and not Path(str(path) + ".gz").is_file():
                    raise ValueError("Supplemental evidence reference is missing")
            except (OSError, ValueError) as exc:
                errors.append({"item_id": ident, "reason": str(exc)})
    return {"errors": errors, "repairs": repairs, "coverage_items": len(items), "pack_count": len(packs), "batch_items": len(batches)}


def reconcile(folder: Path, *, repair=False) -> dict:
    folder = folder.resolve()
    path = folder / "coverage.json"
    original = path.read_bytes()
    coverage = json.loads(original.decode("utf-8-sig"))
    result = check_references(folder, coverage, repair=repair)
    result["coverage_sha256_before"] = hashlib.sha256(original).hexdigest()
    result["changed"] = False
    if repair and result["errors"]:
        raise ValueError("Ambiguous, missing or mismatched evidence remains; no coverage file was written")
    if repair and result["repairs"]:
        coverage["evidence_reference_repair"] = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": result["coverage_sha256_before"], "fixed_references": len(result["repairs"]),
            "method": "unique_full_item_id_and_frozen_catalog_sha"}
        raw = (json.dumps(coverage, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".coverage-repair-", delete=False) as f:
            temp = Path(f.name)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        try:
            if path.read_bytes() != original:
                raise ValueError("coverage.json changed during validation; concurrent work retained")
            backup = folder / ("coverage.references-before-" + result["coverage_sha256_before"][:16] + ".json.gz")
            if not backup.exists():
                with gzip.open(backup, "xb") as f:
                    f.write(original)
            if read_bytes(backup) != original:
                raise ValueError("Reference repair backup differs; original retained")
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        result["changed"] = True
    result["coverage_sha256_after"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = reconcile(args.audit_dir, repair=args.repair)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items()}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
