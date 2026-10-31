"""Guarded publication of a prepared QA03 review-catalog add/update bundle.

This publishes catalog JSON only. It never changes question rows, answer keys,
or learning data. Local queue sync happens only after the online deployment and
an independent fresh online postread both match the prepared SHA.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import gzip
import importlib.util
import json
import os
import subprocess
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "work/internal_medicine_residual_recall_r4_20261024/review-catalog-draft"
LOCAL = ROOT / "backend/app/data/question_evidence_review_queue.json"
PREPARED = DRAFT / "prepared-catalog.json"
DELTA = DRAFT / "combined-delta.json"
PLAN = DRAFT / "manifest.json"

def baseline_path(catalog_sha: str) -> Path:
    return DRAFT / f"online-baseline-{catalog_sha[:12]}.json"


def prepare_receipt_path(prepared_sha: str) -> Path:
    return DRAFT / f"prepare-receipt-{prepared_sha[:12]}.json"


def publish_receipt_path(prepared_sha: str) -> Path:
    return DRAFT / f"publish-receipt-{prepared_sha[:12]}.json"

BASE_PATH = ROOT / "backend/scripts/publish_qa03_recall_v2_catalog.py"
spec = importlib.util.spec_from_file_location("qa03_review_catalog_bundle_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import guarded catalog base: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

archive_spec = importlib.util.spec_from_file_location("qa03_catalog_archive", ROOT / "backend/scripts/qa03_catalog_archive.py")
if archive_spec is None or archive_spec.loader is None:
    raise RuntimeError("Cannot load catalog archival safeguards")
archive_util = importlib.util.module_from_spec(archive_spec)
archive_spec.loader.exec_module(archive_util)

READ_ONLY_REMOTE = r'''import hashlib,json,subprocess,urllib.request
run=lambda a:subprocess.check_output(a,stderr=subprocess.STDOUT)
info=json.loads(run(['docker','inspect','medkb-api']))[0]
raw=run(['docker','exec','medkb-api','cat','/srv/app/data/question_evidence_review_queue.json'])
try:
 with urllib.request.urlopen('http://127.0.0.1:8899/api/health',timeout=5) as r:health={'status':r.status,'body':r.read().decode('utf-8','replace')}
except Exception as e:health={'error':str(e)}
state=info.get('State',{})
print(json.dumps({'captured_online_read_only':True,'image_id':info.get('Image'),'container_running':state.get('Running'),
 'container_status':state.get('Status'),'catalog_sha256':hashlib.sha256(raw).hexdigest(),
 'catalog_items':len(json.loads(raw)['items']),'health':health},ensure_ascii=False))
'''


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def item_sha(item: dict) -> str:
    return sha(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def python_string_expression(value: str, chunk_size: int = 1024) -> str:
    """Represent a large string as adjacent literals, avoiding multi-megabyte source lines."""
    chunks = [value[i : i + chunk_size] for i in range(0, len(value), chunk_size)]
    if not chunks:
        return "''"
    return "(\n" + "\n".join("    " + repr(chunk) for chunk in chunks) + "\n)"


def artifact_bytes(path: Path) -> bytes:
    """Completed batches keep full payloads compressed; active batches keep JSON."""
    return archive_util.artifact_bytes(path)


def archive_completed_payload(path: Path, expected: bytes) -> Path:
    return archive_util.archive_payload(path, expected)


def archive_consumed_inputs(receipt_path: Path, plan: dict, delta: dict, prepared_raw: bytes) -> dict:
    """Archival is post-publication housekeeping; a deferred input is not a failed deployment."""
    if not archive_util.declared_sources(plan, delta):
        return {"status": "no_declared_children", "archived_count": 0, "skipped_count": 0}
    protected = archive_util.pending_reference_dirs(ROOT)
    candidates = archive_util.candidate_inputs(ROOT, receipt_path, plan, delta, prepared_raw,
                                               protected_dirs=protected)
    audit_path = DRAFT / f"consumed-inputs-{sha(prepared_raw)[:12]}.json"
    with audit_path.open("x", encoding="utf-8") as stream:
        json.dump(candidates, stream, ensure_ascii=False, indent=2)
    result = archive_util.archive_consumed(ROOT, candidates, apply=True)
    result_path = audit_path.with_name(audit_path.stem + "-result.json")
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return {"archived_count": len(result["archived"]), "skipped_count": len(result["skipped"]),
            "plan": audit_path.relative_to(ROOT).as_posix(), "result": result_path.relative_to(ROOT).as_posix()}


def read_online() -> dict:
    return base.ssh_python(READ_ONLY_REMOTE)


def capture_baseline() -> dict:
    local_sha = sha(LOCAL.read_bytes())
    path = baseline_path(local_sha)
    remote = read_online()
    if remote.get("captured_online_read_only") is not True:
        raise ValueError("Remote capture is not explicitly read-only")
    if remote.get("catalog_sha256") != local_sha:
        raise ValueError("Local and online catalogs differ; reconcile before preparing a bundle")
    if remote.get("container_running") is not True or remote.get("health", {}).get("status") != 200:
        raise ValueError("Online service/container health check failed")
    record = {**remote, "local_catalog_sha256": local_sha, "local_item_count": len(json.loads(LOCAL.read_bytes())["items"])}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("catalog_sha256") != remote.get("catalog_sha256") or old.get("image_id") != remote.get("image_id"):
            raise ValueError("Online baseline changed since its prior capture")
    else:
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def validate_artifacts() -> tuple[dict, dict, dict, dict, dict]:
    base_raw, prepared_raw, delta_raw, plan_raw = LOCAL.read_bytes(), artifact_bytes(PREPARED), DELTA.read_bytes(), PLAN.read_bytes()
    current_sha, prepared_sha = sha(base_raw), sha(prepared_raw)
    current_baseline = baseline_path(current_sha)
    if not current_baseline.is_file():
        raise FileNotFoundError("Fresh online baseline required; capture it before preparing")
    baseline = json.loads(current_baseline.read_text(encoding="utf-8"))
    if current_sha != baseline.get("local_catalog_sha256") or current_sha != baseline.get("catalog_sha256"):
        raise ValueError("Local or online baseline changed since capture")
    if baseline.get("container_running") is not True or baseline.get("health", {}).get("status") != 200:
        raise ValueError("Captured baseline health was not green")
    base_cat, prepared_cat = json.loads(base_raw), json.loads(prepared_raw)
    delta, plan = json.loads(delta_raw), json.loads(plan_raw)
    if delta.get("production_write_performed") or delta.get("catalog_published") or plan.get("production_write_performed"):
        raise ValueError("Draft artifacts unexpectedly claim a production write")
    if delta.get("baseline_catalog_sha256") != current_sha or plan.get("baseline_catalog_sha256") != current_sha:
        raise ValueError("Delta/plan baseline SHA differs from local and online catalog")
    if delta.get("prepared_catalog_sha256") != prepared_sha or plan.get("prepared_catalog_sha256") != prepared_sha:
        raise ValueError("Delta/plan prepared SHA differs from prepared catalog")
    if len(base_cat.get("items", [])) != baseline.get("catalog_items") or len(base_cat.get("items", [])) != plan.get("base_item_count"):
        raise ValueError("Baseline item count mismatch")
    if len(prepared_cat.get("items", [])) != plan.get("prepared_item_count") or len(prepared_cat.get("items", [])) != delta.get("prepared_item_count"):
        raise ValueError("Prepared item count mismatch")
    if base_cat.get("dataset_id") != prepared_cat.get("dataset_id"):
        raise ValueError("Dataset ID changed")
    base_metadata = {key: value for key, value in base_cat.items() if key != "items"}
    prepared_metadata = {key: value for key, value in prepared_cat.items() if key != "items"}
    if prepared_metadata != base_metadata:
        raise ValueError("Prepared catalog changed top-level metadata outside the item allowlist")
    old = {i["id"]: i for i in base_cat["items"]}
    new = {i["id"]: i for i in prepared_cat["items"]}
    if len(old) != len(base_cat["items"]) or len(new) != len(prepared_cat["items"]):
        raise ValueError("Catalog has duplicate item IDs")
    if not set(old).issubset(new):
        raise ValueError("Bundle removes existing catalog items")
    entries = delta.get("entries", [])
    ids = [e.get("item_id") for e in entries]
    if len(ids) != len(set(ids)) or set(ids) != set(plan.get("changed_item_ids", [])):
        raise ValueError("Entry IDs do not match the exact changed-item plan")
    if len(entries) != plan.get("changed_item_count") or len(entries) != delta.get("changed_item_count"):
        raise ValueError("Changed item count does not match allowlist")
    adds, updates = set(), set()
    for entry in entries:
        ident = entry["item_id"]
        if ident not in new or entry.get("prepared_item") != new[ident]:
            raise ValueError(f"Delta payload differs from prepared item: {ident}")
        if entry.get("prepared_item_sha256") != item_sha(new[ident]):
            raise ValueError(f"Prepared item hash mismatch: {ident}")
        if entry["operation"] == "add":
            if ident in old:
                raise ValueError(f"Add item already exists in baseline: {ident}")
            adds.add(ident)
        elif entry["operation"] == "update":
            if ident not in old or item_sha(old[ident]) != entry.get("expected_before_sha256"):
                raise ValueError(f"Update baseline item hash mismatch: {ident}")
            updates.add(ident)
        else:
            raise ValueError(f"Unsupported catalog operation: {entry.get('operation')}")
    actual_adds = set(new) - set(old)
    actual_updates = {ident for ident in set(old) & set(new) if old[ident] != new[ident]}
    if adds != actual_adds or updates != actual_updates:
        raise ValueError("Prepared catalog contains changes outside the exact add/update allowlist")
    if adds != set(delta.get("added_item_ids", [])) or updates != set(delta.get("updated_item_ids", [])):
        raise ValueError("Delta operation allowlist does not match prepared changes")
    return baseline, base_cat, prepared_cat, delta, plan


def make_remote(baseline: dict, prepared_raw: bytes, prepared: dict, delta: dict) -> str:
    old_guard = "if old_catalog['dataset_id']!=new_catalog['dataset_id'] or not all(by_id.get(i['id'])==i for i in old_catalog['items']):\n raise ValueError('existing catalog items or dataset changed')"
    replacement = r'''old_items={i['id']:i for i in old_catalog['items']}
new_items={i['id']:i for i in new_catalog['items']}
changes=CHANGE_MANIFEST
expected_ids=set(old_items)|set(changes['adds'])
old_metadata={k:v for k,v in old_catalog.items() if k!='items'}
new_metadata={k:v for k,v in new_catalog.items() if k!='items'}
if old_metadata!=new_metadata or set(new_items)!=expected_ids:raise ValueError('catalog metadata or allowlisted item IDs changed')
if set(changes['updates'])&set(changes['adds']):raise ValueError('update/add allowlists overlap')
if set(changes['updates'])-set(old_items) or set(changes['adds'])&set(old_items):raise ValueError('allowlist does not match baseline membership')
for ident,old in old_items.items():
 if ident in changes['updates']:
  pair=changes['updates'][ident]
  if hashlib.sha256(json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()!=pair['before']:raise ValueError('updated baseline item changed: '+ident)
  if hashlib.sha256(json.dumps(new_items[ident],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()!=pair['after']:raise ValueError('prepared update item changed: '+ident)
 elif new_items.get(ident)!=old:raise ValueError('non-allowlisted existing catalog item changed: '+ident)
for ident,after in changes['adds'].items():
 if hashlib.sha256(json.dumps(new_items[ident],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()!=after:raise ValueError('prepared new item changed: '+ident)
for ident in set(changes['updates'])|set(changes['adds']):
 item=new_items[ident];review=item.get('review',{})
 if review.get('status')=='excluded' and (item.get('evidence_pending') is True or (review.get('answer_conflict_found') and not review.get('answer_conflict_resolved'))):raise ValueError('unresolved item cannot be excluded: '+ident)
'''
    if old_guard not in base.REMOTE:
        raise ValueError("Upstream preservation guard changed; refusing to generate a catalog publication payload")
    remote = base.REMOTE.replace(old_guard, replacement, 1)
    manifest = {
        "updates": {e["item_id"]: {"before": e["expected_before_sha256"], "after": e["prepared_item_sha256"]}
                    for e in delta["entries"] if e["operation"] == "update"},
        "adds": {e["item_id"]: e["prepared_item_sha256"] for e in delta["entries"] if e["operation"] == "add"},
        "removes": {},
    }
    remote = remote.replace("expected=CATALOG_SHA\n", "expected=CATALOG_SHA\nCHANGE_MANIFEST=CHANGE_MANIFEST_DATA\n", 1)
    remote = remote.replace("BASELINE_DATA", repr(baseline), 1)
    compressed_catalog_b64 = base64.b64encode(zlib.compress(prepared_raw)).decode("ascii")
    remote = remote.replace("CATALOG_B64", python_string_expression(compressed_catalog_b64), 1)
    remote = remote.replace("CATALOG_SHA", repr(sha(prepared_raw)))
    release = f"/opt/medkb-v2/qa03-review-bundle-{sha(prepared_raw)[:12]}"
    remote = remote.replace("RELEASE_PATH", repr(release))
    remote = remote.replace("medkb-api:recall-v2-base-20261019", f"medkb-api:qa03-review-bundle-{sha(prepared_raw)[:12]}-base")
    remote = remote.replace("medkb-api:question-recall-v2-20261019", f"medkb-api:qa03-review-bundle-{sha(prepared_raw)[:12]}")
    remote = remote.replace("medkb-api:before-recall-v2-20261019", f"medkb-api:before-qa03-review-bundle-{sha(prepared_raw)[:12]}")
    remote = remote.replace("timeout=120", "timeout=600", 1)
    remote = remote.replace("'legacy_items_preserved':len(old_catalog['items'])", "'legacy_items_preserved':len(old_catalog['items'])-len(CHANGE_MANIFEST['updates'])", 1)
    remote = remote.replace("CHANGE_MANIFEST_DATA", repr(manifest), 1)
    compile(remote, "<qa03-review-catalog-bundle>", "exec")
    return remote


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture-baseline", action="store_true")
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.capture_baseline:
        print(json.dumps({"mode": "capture-baseline", "baseline": capture_baseline()}, ensure_ascii=False, indent=2))
        return
    baseline, base_cat, prepared, delta, plan = validate_artifacts()
    prepared_raw = artifact_bytes(PREPARED)
    remote = make_remote(baseline, prepared_raw, prepared, delta)
    if args.prepare_only:
        prepare_receipt = prepare_receipt_path(sha(prepared_raw))
        receipt = {"mode": "prepare-only", "production_write_performed": False,
                   "baseline_catalog_sha256": baseline["catalog_sha256"],
                   "prepared_catalog_sha256": sha(prepared_raw),
                   "changed_item_ids": sorted(e["item_id"] for e in delta["entries"]),
                   "changed_item_count": len(delta["entries"]),
                   "added_count": len(delta.get("added_item_ids", [])),
                   "updated_count": len(delta.get("updated_item_ids", [])),
                   "prepared_item_count": len(prepared["items"]), "remote_payload_syntax_valid": True,
                   "exact_allowlist_valid": True,
                   "prepared_artifact_path": PREPARED.relative_to(ROOT).as_posix(),
                   "delta_artifact_path": DELTA.relative_to(ROOT).as_posix()}
        prepare_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return
    prepared_sha = sha(prepared_raw)
    prepare_receipt = prepare_receipt_path(prepared_sha)
    publish_receipt = publish_receipt_path(prepared_sha)
    if publish_receipt.exists():
        raise FileExistsError(publish_receipt)
    if not prepare_receipt.is_file():
        raise FileNotFoundError("Prepare-only receipt required before publication")
    prepared_receipt = json.loads(prepare_receipt.read_text(encoding="utf-8"))
    if prepared_receipt.get("prepared_catalog_sha256") != sha(prepared_raw) or prepared_receipt.get("baseline_catalog_sha256") != baseline["catalog_sha256"]:
        raise ValueError("Prepare-only receipt no longer matches these artifacts")
    result = subprocess.run(base.SSH_PREFIX + ["python3", "-"], input=remote.encode("utf-8"), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=720)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-7000:])
    deployment = json.loads(result.stdout.decode("utf-8"))
    expected_sha = prepared_sha
    if deployment.get("deployed") is not True or deployment.get("health_passed") is not True or deployment.get("catalog_sha256") != expected_sha or deployment.get("total_question_review_items") != len(prepared["items"]):
        raise RuntimeError("Online deployment did not match prepared catalog; inspect server release receipt")
    receipt = {"production_write_performed": True, "local_catalog_sync_performed": False,
               "baseline_catalog_sha256": baseline["catalog_sha256"], "prepared_catalog_sha256": expected_sha,
               "changed_item_ids": sorted(e["item_id"] for e in delta["entries"]), "deployment": deployment,
               "artifact_paths": {"prepared": PREPARED.relative_to(ROOT).as_posix(),
                                  "delta": DELTA.relative_to(ROOT).as_posix(), "manifest": PLAN.relative_to(ROOT).as_posix()}}
    publish_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Only sync after an independently refreshed online read confirms the deployed SHA.
    post = read_online()
    if post.get("catalog_sha256") != expected_sha or post.get("container_running") is not True or post.get("health", {}).get("status") != 200:
        raise RuntimeError("Online postread did not match deployment; local catalog left untouched")
    local_raw = LOCAL.read_bytes()
    if sha(local_raw) != baseline["local_catalog_sha256"]:
        raise RuntimeError("Local catalog changed after publication; preserved backup not written and sync skipped")
    backup = DRAFT / f"question_evidence_review_queue.before-{baseline['catalog_sha256'][:12]}.json.gz"
    if backup.exists():
        raise FileExistsError(backup)
    with gzip.open(backup, "xb") as f:
        f.write(local_raw)
    with tempfile.NamedTemporaryFile(dir=LOCAL.parent, prefix=LOCAL.name + ".", suffix=".tmp", delete=False) as f:
        temp = Path(f.name)
        f.write(prepared_raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, LOCAL)
    if sha(LOCAL.read_bytes()) != expected_sha:
        raise RuntimeError("Local catalog sync hash mismatch; backup retained")
    receipt.update({"local_catalog_sync_performed": True, "local_backup_path": backup.relative_to(ROOT).as_posix(),
                    "online_postread": post, "local_synced_sha256": expected_sha})
    publish_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Archive only after deployment, independent verification and local sync all succeeded.
    try:
        archived = archive_completed_payload(PREPARED, prepared_raw)
        receipt["prepared_archive_path"] = archived.relative_to(ROOT).as_posix()
    except (OSError, ValueError) as exc:
        receipt["prepared_archival"] = {"status": "deferred", "reason": str(exc)}
    publish_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        receipt["consumed_inputs_archival"] = archive_consumed_inputs(publish_receipt, plan, delta, prepared_raw)
    except Exception as exc:
        receipt["consumed_inputs_archival"] = {"status": "deferred", "reason": str(exc)}
    publish_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"deployed": True, "catalog_sha256": expected_sha, "health_passed": True,
                      "local_catalog_sync_performed": True, "changed_item_count": len(delta["entries"]),
                      "consumed_inputs_archival": receipt["consumed_inputs_archival"],
                      "prepared_archival": receipt.get("prepared_archival", {"status": "archived"}),
                      "receipt": publish_receipt.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
