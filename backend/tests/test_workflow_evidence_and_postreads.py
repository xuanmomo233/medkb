import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def tool_module(name):
    path = Path(__file__).resolve().parents[2] / "tools" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


evidence = module("audit_evidence_integrity")
monitor = module("cas_postread_associations")
archive = module("qa03_catalog_archive")
maintenance = tool_module("maintain-vps-storage.py")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def audit(tmp_path):
    ident = "full-item-id-with-long-suffix"
    coverage = {"catalog_baseline": {"sha256": "frozen"}, "items": {
        ident: {"evidence_pack": "gpt-adjudication/" + ident + ".json", "batch_file": "batches/a.json", "medical_status": "pending"}}}
    write(tmp_path / "coverage.json", coverage)
    pack = write(tmp_path / "gpt-adjudication/short-name.json", {"item_id": ident, "catalog_sha256": "frozen", "decision": "pending"})
    write(tmp_path / "batches/a.json", {"items": [{"item_id": ident, "conflict_verdict": "true_conflict"}]})
    return tmp_path, ident, pack


def test_reference_repair_uses_full_identity_and_preserves_decision(audit):
    folder, ident, pack = audit
    original_pack = pack.read_bytes()
    result = evidence.reconcile(folder, repair=True)
    assert result["changed"] and not result["errors"]
    row = evidence.read_json(folder / "coverage.json")["items"][ident]
    assert row["evidence_pack"] == "gpt-adjudication/short-name.json" and row["medical_status"] == "pending"
    assert pack.read_bytes() == original_pack
    assert list(folder.glob("coverage.references-before-*.json.gz"))
    assert not evidence.reconcile(folder)["errors"]


def test_pack_names_use_entire_identity_and_are_windows_path_friendly():
    first = "same-prefix-" * 20 + "a"
    second = "same-prefix-" * 20 + "b"
    assert evidence.evidence_pack_filename(first) != evidence.evidence_pack_filename(second)
    assert len(evidence.evidence_pack_filename(first)) < 90


@pytest.mark.parametrize("fault", ["missing", "duplicate", "wrong_sha", "wrong_batch", "escape"])
def test_reference_defects_fail_without_rewriting_coverage(audit, fault):
    folder, ident, pack = audit
    if fault == "missing":
        pack.unlink()
    elif fault == "duplicate":
        write(pack.parent / "duplicate.json", evidence.read_json(pack))
    elif fault == "wrong_sha":
        write(pack, {"item_id": ident, "catalog_sha256": "another scan"})
    elif fault == "wrong_batch":
        write(folder / "batches/b.json", {"items": []})
        data = evidence.read_json(folder / "coverage.json")
        data["items"][ident]["batch_file"] = "batches/b.json"
        write(folder / "coverage.json", data)
    else:
        data = evidence.read_json(folder / "coverage.json")
        data["items"][ident]["evidence_pack"] = "../outside.json"
        write(folder / "coverage.json", data)
    before = (folder / "coverage.json").read_bytes()
    with pytest.raises(ValueError):
        evidence.reconcile(folder, repair=True)
    assert (folder / "coverage.json").read_bytes() == before


def test_gzip_evidence_pack_remains_valid(audit):
    folder, ident, pack = audit
    archived = Path(str(pack) + ".gz")
    archived.write_bytes(gzip.compress(pack.read_bytes()))
    pack.unlink()
    assert not evidence.reconcile(folder, repair=True)["errors"]
    assert evidence.read_json(folder / "coverage.json")["items"][ident]["evidence_pack"].endswith(".json.gz")


def test_missing_frozen_baseline_never_guesses_a_reference(audit):
    folder, _, _ = audit
    value = evidence.read_json(folder / "coverage.json")
    value.pop("catalog_baseline")
    write(folder / "coverage.json", value)
    with pytest.raises(ValueError):
        evidence.reconcile(folder, repair=True)


def publication(before, after):
    return {"baseline_catalog_sha256": before, "prepared_catalog_sha256": after,
            "production_write_performed": True, "local_catalog_sync_performed": True,
            "local_synced_sha256": after, "deployment": {"deployed": True, "health_passed": True},
            "online_postread": {"catalog_sha256": after, "container_running": True, "health": {"status": 200}}}


def test_publication_chain_stops_at_recorded_snapshot_not_latest_live(tmp_path):
    write(tmp_path / "publish-receipt-a.json", publication("scan", "reconciled"))
    write(tmp_path / "publish-receipt-b.json", publication("reconciled", "new-live"))
    chain = evidence.publication_chain(tmp_path, "scan", "reconciled")
    assert len(chain) == 1 and chain[-1]["prepared_catalog_sha256"] == "reconciled"


def test_unverified_publication_cannot_bridge_frozen_chain(tmp_path):
    value = publication("scan", "reconciled")
    value["local_catalog_sync_performed"] = False
    write(tmp_path / "publish-receipt-a.json", value)
    with pytest.raises(ValueError, match="fully verified publication chain"):
        evidence.publication_chain(tmp_path, "scan", "reconciled")


def test_new_publication_does_not_invalidate_frozen_reconciliation(tmp_path):
    frozen = b'{"items": []}'
    frozen_sha = hashlib.sha256(frozen).hexdigest()
    live = tmp_path / "current.json"
    live.write_bytes(b'{"items": [{"id":"new"}]}')
    folder = tmp_path / "work/audit"
    folder.mkdir(parents=True)
    archived = folder / "prepared.json.gz"
    archived.write_bytes(gzip.compress(frozen))
    write(folder / "publish-receipt-frozen.json", {"prepared_catalog_sha256": frozen_sha,
          "prepared_archive_path": "work/audit/prepared.json.gz"})
    assert evidence.find_reconciliation_snapshot(folder, tmp_path, live, frozen_sha) == frozen
    assert b'"new"' in live.read_bytes()


def archive_plan(tmp_path):
    item = {"id": "item-1", "question": "synthetic"}
    item_sha = archive.item_digest(item)
    catalog_raw = json.dumps({"items": [item]}, separators=(",", ":")).encode()
    catalog_sha = archive.digest(catalog_raw)
    child = tmp_path / "work/child"
    child.mkdir(parents=True)
    candidate = child / "prepared-catalog-child.json"
    candidate.write_bytes(catalog_raw)
    prepare = write(child / "prepare-receipt-child.json", {"mode": "prepare-only"})
    delta = write(child / "combined-delta-child.json", {"source": "synthetic"})
    receipt_data = publication("before", catalog_sha)
    receipt_data["deployment"]["catalog_sha256"] = catalog_sha
    receipt = write(tmp_path / "work/publish-receipt-parent.json", receipt_data | {
        "prepared_catalog_sha256": catalog_sha, "changed_item_ids": ["item-1"]})
    plan = {"publication_receipt": str(receipt.relative_to(tmp_path)),
            "publication_receipt_sha256": archive.digest(receipt.read_bytes()),
            "candidates": [{"path": str(candidate.relative_to(tmp_path)), "sha256": archive.digest(catalog_raw),
                "bytes": len(catalog_raw), "mtime_ns": candidate.stat().st_mtime_ns,
                "prepare_receipt": str(prepare.relative_to(tmp_path)),
                "prepare_receipt_sha256": archive.digest(prepare.read_bytes()),
                "source_delta": str(delta.relative_to(tmp_path)),
                "source_delta_sha256": archive.digest(delta.read_bytes())}], "skipped": []}
    return child, candidate, delta, plan


def test_archive_apply_rechecks_active_manifest_references(tmp_path):
    child, candidate, delta, plan = archive_plan(tmp_path)
    write(tmp_path / "work/active/manifest-active.json", {
        "prepared_catalog_sha256": "not-yet-published",
        "source_deltas": [str(delta.relative_to(tmp_path))],
    })
    result = archive.archive_consumed(tmp_path, plan, apply=True)
    assert not result["archived"]
    assert candidate.is_file()
    assert "active or unfinished consumer" in result["skipped"][-1]["reason"]


def test_archive_apply_retains_input_when_prepare_receipt_changes(tmp_path):
    _, candidate, _, plan = archive_plan(tmp_path)
    Path(tmp_path / plan["candidates"][0]["prepare_receipt"]).write_text("{} ", encoding="utf-8")
    result = archive.archive_consumed(tmp_path, plan, apply=True)
    assert not result["archived"]
    assert candidate.is_file()
    assert "Consumption evidence changed" in result["skipped"][-1]["reason"]


def test_archive_apply_retains_input_when_existing_gzip_is_corrupt(tmp_path):
    _, candidate, _, plan = archive_plan(tmp_path)
    Path(str(candidate) + ".gz").write_bytes(gzip.compress(b"different payload"))
    result = archive.archive_consumed(tmp_path, plan, apply=True)
    assert not result["archived"]
    assert candidate.is_file()
    assert "Compressed payload verification failed" in result["skipped"][-1]["reason"]


def test_archive_apply_retains_input_when_publication_receipt_is_incomplete(tmp_path):
    _, candidate, _, plan = archive_plan(tmp_path)
    receipt = tmp_path / plan["publication_receipt"]
    value = archive.read_json(receipt)
    value["local_catalog_sync_performed"] = False
    write(receipt, value)
    plan["publication_receipt_sha256"] = archive.digest(receipt.read_bytes())
    result = archive.archive_consumed(tmp_path, plan, apply=True)
    assert not result["archived"]
    assert candidate.is_file()
    assert "Publication receipt is no longer verified" in result["skipped"][-1]["reason"]


def test_archive_apply_writes_verified_gzip_before_removing_original(tmp_path):
    _, candidate, _, plan = archive_plan(tmp_path)
    original = candidate.read_bytes()
    result = archive.archive_consumed(tmp_path, plan, apply=True)
    saved = Path(str(candidate) + ".gz")
    assert len(result["archived"]) == 1
    assert not candidate.exists()
    assert gzip.decompress(saved.read_bytes()) == original


def test_archive_path_traversal_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Parent traversal"):
        archive.safe_path(tmp_path, "../outside.json")
    with pytest.raises(ValueError, match="outside the allowed"):
        archive.safe_path(tmp_path, "backend/private.json")


@pytest.mark.parametrize("fault", ["missing", "wrong_source", "writable", "duplicate"])
def test_mounted_cleanup_rejects_unready_catalog_mount(fault):
    mount = {"Destination": maintenance.DEST, "Source": str(maintenance.SOURCE), "RW": False}
    mounts = [mount]
    if fault == "missing":
        mounts = []
    elif fault == "wrong_source":
        mounts = [{**mount, "Source": "/other/catalog.json"}]
    elif fault == "writable":
        mounts = [{**mount, "RW": True}]
    elif fault == "duplicate":
        mounts = [mount, mount]
    with pytest.raises(ValueError, match="Readonly catalog bind mount is not ready"):
        maintenance.validate_catalog_mount({"Mounts": mounts})


def test_mounted_cleanup_accepts_only_expected_readonly_bind_mount():
    maintenance.validate_catalog_mount({"Mounts": [{
        "Destination": maintenance.DEST, "Source": str(maintenance.SOURCE), "RW": False,
    }]})


def test_success_receipt_requires_deploy_sync_and_matching_postread_sha():
    value = publication("before", "prepared")
    value["deployment"]["catalog_sha256"] = "prepared"
    assert archive.verified_publication(value)
    for mutate in (
        lambda row: row.update(local_catalog_sync_performed=False),
        lambda row: row.update(local_synced_sha256="different"),
        lambda row: row["deployment"].update(deployed=False),
        lambda row: row["deployment"].update(rolled_back=True),
        lambda row: row["online_postread"].update(catalog_sha256="different"),
    ):
        invalid = json.loads(json.dumps(value))
        mutate(invalid)
        assert not archive.verified_publication(invalid)


def test_candidate_scan_stops_at_global_bound(tmp_path):
    item = {"id": "item-1", "question": "synthetic item"}
    item_sha = archive.item_digest(item)
    catalog_raw = json.dumps({"items": [item]}, separators=(",", ":")).encode()
    catalog_sha = archive.digest(catalog_raw)
    work = tmp_path / "work"
    child = work / "child"
    child.mkdir(parents=True)
    parent_publication = publication("base", catalog_sha)
    parent_publication["deployment"]["catalog_sha256"] = catalog_sha
    parent_receipt = write(work / "publish-receipt-parent.json", parent_publication | {
        "prepared_catalog_sha256": catalog_sha, "changed_item_ids": ["item-1"]})
    parent_plan = {"prepared_catalog_sha256": catalog_sha, "changed_item_ids": ["item-1"],
                   "source_deltas": ["work/child/combined-delta-child.json"]}
    parent_delta = {"prepared_catalog_sha256": catalog_sha, "entries": [
        {"item_id": "item-1", "prepared_item_sha256": item_sha}]}
    child_raw = catalog_raw
    child_sha = archive.digest(child_raw)
    write(child / "prepare-receipt-child.json", {
        "mode": "prepare-only", "exact_allowlist_valid": True, "production_write_performed": False,
        "prepared_catalog_sha256": child_sha, "baseline_catalog_sha256": "child-base",
        "changed_item_ids": ["item-1"], "changed_item_count": 1,
    })
    child_delta = {"prepared_catalog_sha256": child_sha, "baseline_catalog_sha256": "child-base",
                   "entries": [{"item_id": "item-1", "operation": "update",
                                "prepared_item": item, "prepared_item_sha256": item_sha}]}
    write(child / "combined-delta-child.json", child_delta)
    (child / "prepared-catalog-one.json").write_bytes(child_raw)
    (child / "prepared-catalog-two.json").write_bytes(child_raw)
    result = archive.candidate_inputs(tmp_path, parent_receipt, parent_plan, parent_delta, catalog_raw,
                                      max_candidates=1)
    assert len(result["candidates"]) == 1
    assert any("Global candidate limit reached" in row["reason"] for row in result["skipped"])


def test_cleanup_entrypoint_has_no_mount_migration_or_container_recreate():
    root = Path(__file__).resolve().parents[2]
    source = (root / "tools/maintain-vps-storage.py").read_text(encoding="utf-8")
    assert "docker', 'compose" not in source
    assert "force-recreate" not in source
    assert "Readonly catalog bind mount is not ready" in source


def test_concurrent_coverage_update_is_never_overwritten(audit, monkeypatch):
    folder, _, _ = audit
    original = evidence.tempfile.NamedTemporaryFile
    class ConcurrentUpdate:
        def __init__(self, **kwargs):
            self.context = original(**kwargs)
        def __enter__(self):
            return self.context.__enter__()
        def __exit__(self, *args):
            result = self.context.__exit__(*args)
            current = evidence.read_json(folder / "coverage.json")
            current["other_session_update"] = True
            write(folder / "coverage.json", current)
            return result
    monkeypatch.setattr(evidence.tempfile, "NamedTemporaryFile", ConcurrentUpdate)
    with pytest.raises(ValueError, match="changed during validation"):
        evidence.reconcile(folder, repair=True)
    assert evidence.read_json(folder / "coverage.json")["other_session_update"] is True


@pytest.fixture
def operation(tmp_path):
    root = tmp_path.resolve()
    def add(name, data):
        return monitor.load(write(root / name, data))
    before = {"mode": "REPEATABLE READ READ ONLY", "production_write_performed": False,
              "snapshot": "10:10:", "catalog_sha256": "sha", "closure_ids": [1, 2],
              "mappings": [], "protected_target_rows": {"plan_tasks": [{"id": 7, "target_id": 1, "due_day": "2026-10-28"}]}}
    post = {**before, "snapshot": "12:12:", "mappings": [{"alias_id": 1, "canonical_id": 2}]}
    receipt = {"committed": True, "batch_id": "batch", "catalog_sha256": "sha", "prewrite_snapshot": "10:10:",
               "edge": {"alias_id": 1, "canonical_id": 2}, "prewrite_capture": "before.json"}
    return root, add, before, post, receipt


def result(operation, *, post_changes=None, explicit=True, nested=False):
    root, add, before, post, receipt = operation
    post = {**post, **(post_changes or {})}
    if explicit:
        receipt["postread_capture"] = "observed-state.json"
    commit = add("cas-result.json", {"result": receipt} if nested else receipt)
    nodes = [commit, add("before.json", before), add("observed-state.json", post)]
    return monitor.associate(root, nodes)["results"][0]


def test_explicit_nested_receipt_links_non_postread_filename(operation):
    row = result(operation, nested=True)
    assert row["status"] == "associated_readonly_postread"
    assert row["association"] == "explicit_reference"
    assert row["plan_task_verification"]["status"] == "compared"


@pytest.mark.parametrize("change", [
    {"catalog_sha256": "wrong"}, {"snapshot": "9:9:"},
    {"mappings": [{"alias_id": 1, "canonical_id": 3}]},
    {"mappings": [{"alias_id": 1, "canonical_id": 2}, {"alias_id": 2, "canonical_id": 3}]},
    {"production_write_performed": True}, {"batch_id": "different batch"},
])
def test_wrong_sha_old_snapshot_wrong_edge_or_write_cannot_close_cas(operation, change):
    assert result(operation, post_changes=change)["status"] == "postread_mismatch"


def test_same_directory_older_capture_is_not_a_postread(operation):
    row = result(operation, post_changes={"snapshot": "8:8:"}, explicit=False)
    assert row["status"] != "associated_readonly_postread"


def test_multiple_plausible_captures_are_ambiguous(operation):
    root, add, before, post, receipt = operation
    nodes = [add("cas.json", receipt), add("before.json", before), add("state1.json", post),
             add("state2.json", {**post, "snapshot": "13:13:"})]
    assert monitor.associate(root, nodes)["results"][0]["status"] == "ambiguous_postreads"


def test_explicit_reference_wins_over_other_plausible_captures(operation):
    root, add, before, post, receipt = operation
    receipt["postread_path"] = "state1.json"
    nodes = [add("cas.json", receipt), add("before.json", before), add("state1.json", post), add("state2.json", {**post, "snapshot": "13:13:"})]
    row = monitor.associate(root, nodes)["results"][0]
    assert row["status"] == "associated_readonly_postread" and row["postread"] == "state1.json"


def test_missing_task_capture_is_not_zero_change(operation):
    row = result(operation, post_changes={"protected_target_rows": {}})
    assert row["plan_task_verification"]["status"] == "not_captured"


def test_task_changes_are_recorded_in_matched_scope(operation):
    row = result(operation, post_changes={"protected_target_rows": {"plan_tasks": [{"id": 7, "target_id": 2, "due_day": "2026-10-29"}]}})
    fields = row["plan_task_verification"]["changed"][0]["fields"]
    assert set(fields) == {"target_id", "due_day"}


def test_task_scope_and_columns_must_be_comparable(operation):
    row = result(operation, post_changes={"closure_ids": [1, 2, 3]})
    assert row["plan_task_verification"]["status"] == "scope_mismatch"
    row = result(operation, post_changes={"protected_target_rows": {"plan_tasks": [{"id": 7}]}})
    assert row["plan_task_verification"]["status"] == "incomplete_task_columns"


def test_cas_result_and_linked_summary_are_counted_once(operation):
    root, add, before, post, receipt = operation
    nodes = [add("cas.json", receipt), add("before.json", before), add("state.json", post),
             add("summary.json", {"status": "database_merge_committed_and_independently_read_back", "cas_result": "cas.json", "postread_capture": "state.json"})]
    report = monitor.associate(root, nodes)
    assert report["operation_groups"] == 1
    assert report["results"][0]["status"] == "associated_readonly_postread"


def test_duplicate_strong_batch_receipts_are_counted_once(operation):
    root, add, before, post, receipt = operation
    nodes = [add("cas1.json", receipt), add("cas2.json", receipt), add("before.json", before), add("state.json", post)]
    assert monitor.associate(root, nodes)["operation_groups"] == 1


def test_contradictory_commit_flags_require_review(operation):
    root, add, *_ = operation
    report = monitor.associate(root, [add("bad.json", {"committed": False, "production_write_performed": True})])
    assert report["operation_groups"] == 0 and report["conflicting_commit_claims"]


def test_explicit_postread_hash_mismatch_is_rejected(operation):
    root, add, before, post, receipt = operation
    receipt.update(postread_path="state.json", postread_sha256="wrong digest")
    nodes = [add("cas.json", receipt), add("before.json", before), add("state.json", post)]
    assert monitor.associate(root, nodes)["results"][0]["status"] == "postread_mismatch"


def test_prewrite_hash_mismatch_never_claims_zero_plan_change(operation):
    root, add, before, post, receipt = operation
    receipt.update(postread_path="state.json", capture_sha256="incorrect")
    nodes = [add("cas.json", receipt), add("before.json", before), add("state.json", post)]
    row = monitor.associate(root, nodes)["results"][0]
    assert row["status"] == "explicit_reference_needs_review"
    assert "plan_task_verification" not in row


def test_inline_boolean_is_not_independent_postread(operation):
    root, add, before, post, receipt = operation
    receipt["independent_postread"] = {"ok": True, "snapshot": "12:12:"}
    report = monitor.associate(root, [add("cas.json", receipt), add("before.json", before)])
    assert report["results"][0]["status"] == "postread_not_proven"


def test_plan_group_aliases_are_identity_constraints():
    assert monitor.edges({"groups": [{"root_id": 2, "alias_ids": [1, 3]}]}) == {(1, 2), (3, 2)}


def test_pending_receipt_survives_next_incremental_window(operation):
    root, add, before, post, receipt = operation
    node = add("old-cas.json", receipt)
    previous = write(root / "previous.json", {"results": [
        {"receipt_files": ["old-cas.json"], "status": "postread_not_proven"},
        {"receipt_files": ["already-closed-and-not-needed.json"], "status": "associated_readonly_postread",
         "plan_task_verification": {"status": "compared"}}]})
    carried = monitor.carry_pending(root, [], previous)
    assert len(carried) == 1 and carried[0]["path"] == node["path"]


def test_gzip_postread_reference_is_supported(operation):
    root, add, before, post, receipt = operation
    receipt["postread_capture"] = "state.json"
    encoded = json.dumps(post).encode()
    (root / "state.json.gz").write_bytes(gzip.compress(encoded))
    report = monitor.associate(root, [add("cas.json", receipt), add("before.json", before)])
    assert report["results"][0]["status"] == "associated_readonly_postread"


def test_legacy_database_change_wrapper_is_deduplicated_and_linked(operation):
    root, add, before, post, receipt = operation
    summary = {"status": "database_merge_committed_and_independently_read_back", "database_change": receipt,
               "capture": "before.json", "postread": "state.json"}
    nodes = [add("cas.json", receipt), add("summary.json", summary), add("before.json", before), add("state.json", post)]
    report = monitor.associate(root, nodes)
    assert report["operation_groups"] == 1
    assert report["results"][0]["status"] == "associated_readonly_postread"


def test_linked_legacy_capture_without_readonly_fields_is_not_called_missing(operation):
    root, add, before, post, receipt = operation
    legacy = {k: v for k, v in post.items() if k not in ("mode", "production_write_performed")}
    legacy["independent_readback"] = True
    receipt["postread_path"] = "legacy.json"
    report = monitor.associate(root, [add("cas.json", receipt), add("before.json", before), add("legacy.json", legacy)])
    row = report["results"][0]
    assert row["status"] == "linked_postread_readonly_not_attested"
    assert "plan_task_verification" not in row
