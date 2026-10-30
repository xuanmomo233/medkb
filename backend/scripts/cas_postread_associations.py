"""Offline CAS/postread correlation. File proximity is never verification evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re

MAX_BYTES = 16 * 1024 * 1024
POST_KEYS = {"postread", "postread_path", "postread_capture", "postread_file", "independent_postread", "independent_postread_path", "post_capture"}
CAS_KEYS = {"cas_result", "cas_result_path", "cas_receipt", "production_receipt", "database_apply_receipt", "production_cas_receipt"}
PRE_KEYS = {"prewrite_capture", "capture_path", "prewrite_path", "pre_capture", "capture"}
PLAN_KEYS = {"plan_path", "merge_plan", "cas_plan_path", "plan"}
COMMITTED_STATUSES = {"committed", "merged_and_independently_read_back", "database_merge_committed_and_independently_read_back", "committed_and_verified"}


def compact(data):
    """Keep association/plan metadata, never retain question bodies or full catalogs."""
    result = {k: v for k, v in data.items() if isinstance(v, (str, bool, int, float, type(None)))}
    for key in ("result", "database_change", "commit_result", "edge", "new_edge", "expected_edge", "independent_postread", "batch", "execution_batch", "execution"):
        if isinstance(data.get(key), dict):
            result[key] = compact(data[key])
    if isinstance(data.get("deployment"), dict):
        result["deployment"] = {"present": True}
    for key in ("requested_ids", "closure_ids", "question_ids"):
        if isinstance(data.get(key), list):
            result[key] = data[key]
    if isinstance(data.get("groups"), list):
        result["groups"] = [{k: row[k] for k in ("root_id", "alias_ids") if k in row}
                            for row in data["groups"] if isinstance(row, dict)]
    for key in ("new_edges", "new_mapping_edges", "inserted_edges", "mappings", "question_merges"):
        if isinstance(data.get(key), list):
            result[key] = [{k: r[k] for k in ("alias_id", "canonical_id") if k in r} for r in data[key] if isinstance(r, dict)]
    task_keys = ("id", "task_id", "target_id", "due_day", "position", "completed_at", "kind", "user_id")
    for key in ("plan_tasks", "user2_plan_tasks_all"):
        if isinstance(data.get(key), list):
            result[key] = [{k: r[k] for k in task_keys if k in r} for r in data[key] if isinstance(r, dict)]
    rows = data.get("protected_target_rows", {})
    if isinstance(rows, dict) and isinstance(rows.get("plan_tasks"), list):
        result["protected_target_rows"] = {"plan_tasks": [{k: r[k] for k in task_keys if k in r} for r in rows["plan_tasks"]]}
    return result


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as f:
            raw = f.read(MAX_BYTES + 1)
    else:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Artifact exceeds bounded metadata size")
        raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("Artifact exceeds bounded metadata size")
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Expected metadata object")
    return {"path": path, "data": compact(data), "sha256": sha(raw)}


def view(data):
    result = dict(data)
    for key in ("result", "database_change", "commit_result"):
        if isinstance(data.get(key), dict):
            result.update(view(data[key]))
    return result


def batch_identity(data):
    d = view(data)
    return (d.get("batch_id") or d.get("editorial_batch_id") or d.get("batch", {}).get("id")
            or d.get("execution_batch", {}).get("id") or d.get("execution", {}).get("batch_id"))


def references(data, keys):
    result = []
    for container in [data, view(data)]:
        for key in keys:
            value = container.get(key)
            if isinstance(value, dict):
                value = value.get("path") or value.get("capture_path") or value.get("postread_path")
            if isinstance(value, str) and (value.endswith(".json") or value.endswith(".json.gz")):
                result.append(value)
    return list(dict.fromkeys(result))


def resolve(root, source, ref):
    value = Path(ref)
    if ".." in value.parts:
        raise ValueError("Reference contains parent traversal")
    paths = [value] if value.is_absolute() else [root / value, source.parent / value]
    found = set()
    for path in paths:
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
            if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in [path, *path.parents] if p != root):
                continue
            if resolved.is_file():
                found.add(resolved)
            elif Path(str(resolved) + ".gz").is_file():
                found.add(Path(str(resolved) + ".gz"))
        except (OSError, ValueError):
            continue
    if len(found) != 1:
        raise ValueError("Missing or ambiguous explicit reference: " + ref)
    return next(iter(found))


def catalog_sha(data):
    d = view(data)
    for key in ("catalog_sha256", "catalog_sha256_expected", "prewrite_catalog_sha256", "catalog_baseline_sha256", "baseline_catalog_sha256"):
        if isinstance(d.get(key), str):
            return d[key]


def snapshot(data, *, post=False):
    d = view(data)
    keys = ("postread_snapshot", "post_snapshot", "snapshot") if post else ("prewrite_snapshot", "captured_snapshot", "capture_snapshot", "snapshot")
    return next((d[k] for k in keys if isinstance(d.get(k), str)), None)


def xmax(value):
    try:
        return int(value.split(":")[1])
    except (AttributeError, ValueError, IndexError):
        return None


def edges(data):
    d = view(data)
    result = set()
    if isinstance(d.get("alias_id"), int) and isinstance(d.get("canonical_id"), int):
        result.add((d["alias_id"], d["canonical_id"]))
    for key in ("edge", "new_edge", "new_edges", "expected_edge", "new_mapping_edges", "inserted_edges"):
        value = d.get(key)
        if isinstance(value, dict):
            result.update(edges(value))
        elif isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    result.update(edges(row))
    for group in d.get("groups", []) if isinstance(d.get("groups"), list) else []:
        if isinstance(group.get("root_id"), int):
            result.update((alias, group["root_id"]) for alias in group.get("alias_ids", []) if isinstance(alias, int))
    return result


def committed(data):
    d = view(data)
    if d.get("deployment") or (d.get("prepared_catalog_sha256") and d.get("committed") is not True and not edges(d)):
        return False  # Catalog publications are a different operation, not a database CAS.
    if d.get("rolled_back") is True or d.get("commit_outcome") == "not_committed":
        return False
    if d.get("committed") is False:
        return False
    return d.get("committed") is True or d.get("production_write_performed") is True or d.get("status") in COMMITTED_STATUSES


def readonly(data):
    d = view(data)
    mode = str(d.get("mode") or d.get("capture_mode") or "").upper().replace(" ", "")
    explicit = d.get("transaction_read_only") in (True, "on") or "READONLY" in mode or "RR/RO" in mode
    return d.get("production_write_performed") is False and explicit and xmax(d.get("snapshot")) is not None


def task_rows(data):
    d = view(data)
    if isinstance(d.get("user2_plan_tasks_all"), list):
        return d["user2_plan_tasks_all"], "full_user2_plan"
    protected = d.get("protected_target_rows", {})
    if isinstance(protected, dict) and isinstance(protected.get("plan_tasks"), list):
        return protected["plan_tasks"], sorted(d.get("closure_ids") or d.get("requested_ids") or [])
    if isinstance(d.get("plan_tasks"), list):
        return d["plan_tasks"], sorted(d.get("closure_ids") or d.get("requested_ids") or [])
    return None, None


def task_difference(before, after):
    old, scope_old = task_rows(before)
    new, scope_new = task_rows(after)
    if old is None or new is None:
        return {"status": "not_captured", "scope": "unknown"}
    if scope_old != scope_new or scope_old == []:
        return {"status": "scope_mismatch", "scope": "unknown"}
    if any("target_id" not in row or "due_day" not in row for row in [*old, *new]):
        return {"status": "incomplete_task_columns", "scope": scope_old}
    def keyed(rows):
        result = {}
        for row in rows:
            ident = row.get("id", row.get("task_id"))
            if ident is None or str(ident) in result:
                raise ValueError("Missing or duplicate task identity")
            result[str(ident)] = row
        return result
    try:
        a, b = keyed(old), keyed(new)
    except ValueError as exc:
        return {"status": "invalid_task_rows", "reason": str(exc)}
    changed = []
    for ident in sorted(a.keys() & b.keys()):
        fields = {key: {"before": a[ident].get(key), "after": b[ident].get(key)} for key in
                  ("target_id", "due_day", "position", "completed_at", "kind", "user_id") if a[ident].get(key) != b[ident].get(key)}
        if fields:
            changed.append({"task_id": ident, "fields": fields})
    return {"status": "compared", "scope": scope_old, "before_count": len(a), "after_count": len(b),
            "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": changed}


def match_post(post, expected_sha, expected_edges, pre_snapshot, batch_id, *, explicit, declared_snapshot=None, declared_hash=None):
    d = view(post["data"])
    readonly_reason = None if readonly(d) else "readonly_not_attested"
    if d.get("production_write_performed") is True:
        return "postread_has_write_claim"
    if declared_hash and post["sha256"] != declared_hash:
        return "postread_hash_mismatch"
    if expected_sha is None or catalog_sha(d) != expected_sha:
        return "catalog_sha_mismatch_or_unknown"
    if declared_snapshot and d.get("snapshot") != declared_snapshot:
        return "postread_snapshot_mismatch"
    if xmax(pre_snapshot) is None or xmax(d.get("snapshot")) <= xmax(pre_snapshot):
        return "snapshot_not_after_prewrite_or_unknown"
    if batch_id and batch_identity(d) and batch_identity(d) != batch_id:
        return "batch_identity_mismatch"
    if not explicit and (not batch_id or batch_identity(d) != batch_id):
        # A narrow target+SHA+newer snapshot may be used without filename assumptions.
        if not expected_edges:
            return "insufficient_batch_or_target_identity"
    if expected_edges:
        mappings = d.get("mappings", d.get("question_merges"))
        if not isinstance(mappings, list):
            return "target_mapping_rows_not_captured"
        try:
            mapping = {int(r["alias_id"]): int(r["canonical_id"]) for r in mappings if isinstance(r, dict) and "alias_id" in r and "canonical_id" in r}
        except (ValueError, TypeError):
            return "invalid_mapping_rows"
        def root(i):
            seen = set()
            while i in mapping:
                if i in seen:
                    raise ValueError("mapping cycle")
                seen.add(i)
                i = mapping[i]
            return i
        try:
            if any(alias not in mapping or root(alias) != canonical or root(canonical) != canonical for alias, canonical in expected_edges):
                return "target_mapping_mismatch"
        except ValueError:
            return "target_mapping_cycle"
    return readonly_reason


def associate(root: Path, nodes: list[dict]) -> dict:
    root = root.resolve()
    nodes = list(nodes)
    by_path = {n["path"].resolve(): n for n in nodes}
    # A new verification receipt can explicitly reference an older CAS result.
    for node in list(nodes):
        for ref in references(node["data"], CAS_KEYS):
            try:
                path = resolve(root, node["path"], ref)
                if path not in by_path:
                    linked = load(path)
                    by_path[path] = linked
                    nodes.append(linked)
            except (OSError, ValueError):
                pass
    commits = [n for n in nodes if committed(n["data"])]
    groups = {}
    fingerprints = {}
    for node in commits:
        owner = node["path"]
        for ref in references(node["data"], CAS_KEYS):
            try:
                candidate = resolve(root, node["path"], ref)
                if candidate in by_path and committed(by_path[candidate]["data"]):
                    owner = candidate
                    break
            except ValueError:
                pass
        identity = view(by_path[owner]["data"]) if owner in by_path else view(node["data"])
        identity_edges = edges(identity)
        if identity.get("batch_id") and catalog_sha(identity) and snapshot(identity) and identity_edges:
            fingerprint = (identity["batch_id"], catalog_sha(identity), snapshot(identity), tuple(sorted(identity_edges)))
            owner = fingerprints.setdefault(fingerprint, owner)
        groups.setdefault(owner, []).append(node)
    canonical_of = {node["path"]: owner for owner, members in groups.items() for node in members}
    results = []
    captures = [n for n in nodes if readonly(n["data"])]
    for owner, receipts in groups.items():
        if owner in by_path and by_path[owner] not in receipts:
            receipts.insert(0, by_path[owner])
        # Follow explicit CAS links from supplemental verification receipts too.
        for node in nodes:
            if node in receipts:
                continue
            for ref in references(node["data"], CAS_KEYS):
                try:
                    resolved = resolve(root, node["path"], ref)
                    if canonical_of.get(resolved, resolved) == owner:
                        receipts.append(node)
                        break
                except ValueError:
                    pass
        primary = next((n for n in receipts if n["path"] == owner), receipts[0])
        data = view(primary["data"])
        expected_sha = catalog_sha(data)
        batch_id = batch_identity(data)
        pre_snapshot = snapshot(data)
        expected_edges = set()
        explicit_posts, pre_captures, errors = [], [], []
        declared_snapshot = declared_hash = None
        for node in receipts:
            d = view(node["data"])
            expected_sha = expected_sha or catalog_sha(d)
            batch_id = batch_id or batch_identity(d)
            pre_snapshot = pre_snapshot or snapshot(d)
            expected_edges.update(edges(d))
            declared_snapshot = declared_snapshot or d.get("postread_snapshot") or d.get("post_snapshot")
            declared_hash = declared_hash or d.get("postread_sha256") or d.get("postread_capture_sha256")
            inline_post = d.get("independent_postread")
            if isinstance(inline_post, dict) and references(d, POST_KEYS):
                declared_snapshot = declared_snapshot or inline_post.get("snapshot")
                declared_hash = declared_hash or inline_post.get("sha256")
            for keys, target in [(POST_KEYS, explicit_posts), (PRE_KEYS, pre_captures)]:
                for ref in references(d, keys):
                    try:
                        path = resolve(root, node["path"], ref)
                        linked = by_path.get(path) or load(path)
                        reference_sha = (d.get("capture_sha256") or d.get("prewrite_capture_sha256")) if keys == PRE_KEYS else None
                        if reference_sha and reference_sha != linked["sha256"]:
                            raise ValueError("Declared prewrite capture hash mismatch: " + ref)
                        target.append(linked)
                    except (OSError, ValueError) as exc:
                        errors.append(str(exc))
            for ref in references(d, PLAN_KEYS):
                try:
                    plan_node = load(resolve(root, node["path"], ref))
                    if d.get("plan_sha256") and d["plan_sha256"] != plan_node["sha256"]:
                        raise ValueError("Declared plan hash mismatch: " + ref)
                    plan = plan_node["data"]
                    expected_edges.update(edges(plan))
                    batch_id = batch_id or plan.get("batch_id")
                    pre_snapshot = pre_snapshot or snapshot(plan)
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
        if not pre_captures:
            pre_captures = [n for n in captures if n["data"].get("snapshot") == pre_snapshot and catalog_sha(n["data"]) == expected_sha]
        has_explicit = any(references(n["data"], POST_KEYS) for n in receipts)
        candidates = explicit_posts if has_explicit else captures
        matched, rejected = {}, []
        for post in candidates:
            reason = match_post(post, expected_sha, expected_edges, pre_snapshot, batch_id,
                                explicit=has_explicit, declared_snapshot=declared_snapshot, declared_hash=declared_hash)
            if reason is None:
                matched.setdefault(post["sha256"], post)
            elif has_explicit:
                rejected.append({"path": str(post["path"].relative_to(root)), "reason": reason})
            elif len(rejected) < 5:
                d = view(post["data"])
                aliases = {r.get("alias_id") for r in d.get("mappings", []) if isinstance(r, dict)}
                if (batch_id and d.get("batch_id") == batch_id) or aliases.intersection(a for a, _ in expected_edges):
                    rejected.append({"path": str(post["path"].relative_to(root)), "reason": reason})
        row = {"receipt": str(owner.relative_to(root)), "receipt_files": [str(n["path"].relative_to(root)) for n in receipts],
               "catalog_sha256": expected_sha, "batch_id": batch_id, "prewrite_snapshot": pre_snapshot,
               "expected_edges": [list(e) for e in sorted(expected_edges)], "reference_errors": errors, "rejected": rejected}
        if errors:
            row["status"] = "explicit_reference_needs_review"
        elif len(matched) == 0:
            if has_explicit and rejected and all(r["reason"] == "readonly_not_attested" for r in rejected):
                row["status"] = "linked_postread_readonly_not_attested"
            else:
                row["status"] = "postread_mismatch" if rejected else "postread_not_proven"
        elif len(matched) > 1:
            row["status"] = "ambiguous_postreads"
            row["candidate_paths"] = [str(n["path"].relative_to(root)) for n in matched.values()]
        else:
            post = next(iter(matched.values()))
            row.update(status="associated_readonly_postread", postread=str(post["path"].relative_to(root)),
                       postread_sha256=post["sha256"], postread_snapshot=post["data"]["snapshot"],
                       association="explicit_reference" if has_explicit else "unique_sha_snapshot_and_target_match")
            pre_unique = {n["sha256"]: n for n in pre_captures if readonly(n["data"]) and n["data"].get("snapshot") == pre_snapshot and catalog_sha(n["data"]) == expected_sha}
            row["plan_task_verification"] = task_difference(next(iter(pre_unique.values()))["data"], post["data"]) if len(pre_unique) == 1 else {"status": "prewrite_capture_missing_or_ambiguous"}
            if not expected_edges:
                row["target_verification"] = "batch_linked_only; target mutation contract requires separate validation"
        results.append(row)
    conflicts = [str(n["path"].relative_to(root)) for n in nodes if view(n["data"]).get("committed") is False and view(n["data"]).get("production_write_performed") is True]
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "scope": "local_artifact_evidence_only_not_current_production_state",
            "counting_note": "Operation groups are evidence groups, not a global count of distinct production transactions. Unproven does not mean uncommitted.",
            "conflicting_commit_claims": conflicts,
            "receipt_files": len(commits), "operation_groups": len(results), "statuses": dict(Counter(r["status"] for r in results)), "results": results}


def collect(root: Path, scope: Path, since=None):
    nodes, skipped = [], []
    pattern = re.compile(r"receipt|postread|postcas|rrro|cas-result|cas-apply|independent|capture|postverify|merge-plan|cas-plan", re.I)
    for path in scope.rglob("*.json*"):
        if not pattern.search(path.name) or not (path.name.endswith(".json") or path.name.endswith(".json.gz")):
            continue
        try:
            path.resolve().relative_to(root)
            if since is not None and path.stat().st_mtime < since:
                continue
            nodes.append(load(path.resolve()))
        except (OSError, ValueError) as exc:
            skipped.append({"path": str(path), "reason": str(exc)})
    return nodes, skipped


def carry_pending(root: Path, nodes: list[dict], previous_path: Path):
    if previous_path.stat().st_size > MAX_BYTES:
        raise ValueError("Previous association report exceeds bounded metadata size")
    previous = json.loads(previous_path.read_text(encoding="utf-8-sig"))
    result = list(nodes)
    known = {n["path"] for n in result}
    for row in previous.get("results", []):
        if (row.get("status") == "associated_readonly_postread"
                and row.get("plan_task_verification", {}).get("status") == "compared"
                and not row.get("target_verification")):
            continue
        for ref in row.get("receipt_files", []) or [row.get("receipt")]:
            if not ref:
                continue
            path = resolve(root, previous_path, ref)
            if path not in known:
                result.append(load(path))
                known.add(path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scope", type=Path, default=Path("work"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--since", help="UTC/offset ISO timestamp for incremental local metadata discovery")
    parser.add_argument("--previous-report", type=Path, help="Carry unresolved CAS evidence across incremental monitoring windows")
    args = parser.parse_args()
    root = args.root.resolve()
    scope = args.scope.resolve() if args.scope.is_absolute() else root / args.scope
    scope.resolve().relative_to(root)
    since = None
    if args.since:
        parsed = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parser.error("--since requires an explicit timezone offset")
        since = parsed.timestamp()
    nodes, skipped = collect(root, scope, since)
    before_carry = len(nodes)
    if args.previous_report:
        nodes = carry_pending(root, nodes, args.previous_report.resolve())
    report = associate(root, nodes)
    report["carried_pending_receipts"] = len(nodes) - before_carry
    report["discovery_since"] = args.since
    report["skipped_artifacts"] = skipped
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k not in ("results", "skipped_artifacts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
