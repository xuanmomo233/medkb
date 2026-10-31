"""Generate a proof-based cleanup plan; this command never removes any input."""
import argparse
import collections
from datetime import datetime, timezone
import importlib.util
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qa03_archive_planner", ROOT / "backend/scripts/qa03_catalog_archive.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protected-file", type=Path)
    parser.add_argument("--min-age-seconds", type=int, default=7200)
    parser.add_argument("--receipt", action="append", default=[],
                        help="Limit planning to this verified publish receipt; may be repeated")
    parser.add_argument("--max-publications", type=int, default=250)
    parser.add_argument("--max-candidates", type=int, default=250)
    args = parser.parse_args()
    if args.min_age_seconds < 7200:
        parser.error("Historical cleanup retains at least two hours of in-flight inputs")
    if args.max_publications < 1 or args.max_candidates < 1:
        parser.error("Planning limits must be positive")
    protected = archive.pending_reference_dirs(ROOT)
    if args.protected_file:
        for name in json.loads(args.protected_file.read_text(encoding="utf-8-sig")):
            protected.add(archive.safe_path(ROOT, name, payload=True))
    if args.receipt:
        receipt_paths = []
        for value in args.receipt:
            path = archive.safe_path(ROOT, value)
            if not path.is_file():
                parser.error(f"Publication receipt does not exist: {value}")
            receipt_paths.append(path)
        receipt_rows = []
        for receipt_path in sorted(set(receipt_paths)):
            receipt = archive.read_json(receipt_path)
            if not archive.verified_publication(receipt):
                parser.error(f"Publication receipt is not fully verified: {receipt_path.relative_to(ROOT)}")
            receipt_rows.append((receipt_path, receipt))
    else:
        bounded = list(itertools.islice(archive.published_receipts(ROOT), args.max_publications + 1))
        truncated = len(bounded) > args.max_publications
        receipt_rows = bounded[:args.max_publications]
    if args.receipt and len(receipt_rows) > args.max_publications:
        parser.error("Explicit receipt count exceeds --max-publications")
    considered = receipt_rows
    if args.receipt:
        truncated = False
    seen = set()
    plans = []
    skipped = []
    accepted_candidates = 0
    for receipt_path, receipt in considered:
        try:
            plan, delta, raw = archive.historical_context(ROOT, receipt_path)
            if not archive.declared_sources(plan, delta):
                continue
            result = archive.candidate_inputs(ROOT, receipt_path, plan, delta, raw,
                protected_dirs=protected, min_age_seconds=args.min_age_seconds,
                max_candidates=args.max_candidates - accepted_candidates)
            unique = []
            for row in result["candidates"]:
                if row["path"] not in seen:
                    seen.add(row["path"])
                    if len(seen) <= args.max_candidates:
                        unique.append(row)
                        accepted_candidates += 1
                    else:
                        truncated = True
            result["candidates"] = unique
            plans.append(result)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            skipped.append({"receipt": str(receipt_path.relative_to(ROOT)), "reason": str(exc)})
    output = archive.safe_path(ROOT, str(args.output.resolve()), payload=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 2, "root": str(ROOT), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "min_age_seconds": args.min_age_seconds, "protected_dirs": [str(p.relative_to(ROOT)) for p in sorted(protected)],
                "limits": {"max_publications": args.max_publications, "max_candidates": args.max_candidates,
                           "receipts_explicitly_selected": bool(args.receipt), "truncated": truncated},
                "publications": plans, "skipped_publications": skipped}
    with output.open("x", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    rows = [row for plan in plans for row in plan["candidates"]]
    reasons = collections.Counter(row.get("reason", "") for plan in plans for row in plan["skipped"])
    print(json.dumps({"plan": str(output), "candidate_count": len(rows), "candidate_bytes": sum(r["bytes"] for r in rows),
                      "protected_directories": len(protected), "skipped_reasons": reasons,
                      "candidates": [r["path"] for r in rows]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
