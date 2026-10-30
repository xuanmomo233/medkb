"""Revalidate and optionally archive inputs from a bounded cleanup plan."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qa03_archive_executor", ROOT / "backend/scripts/qa03_catalog_archive.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Write verified gzip archives and remove matching originals")
    args = parser.parse_args()
    plan_path = archive.safe_path(ROOT, str(args.plan.resolve()), payload=True)
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    if plan.get("root") != str(ROOT) or plan.get("schema_version") not in (1, 2):
        parser.error("Unexpected plan root or schema")
    publications = plan.get("publications")
    if not isinstance(publications, list):
        parser.error("Plan publications must be a list")
    cap = plan.get("limits", {}).get("max_candidates", 250)
    count = sum(len(row.get("candidates", [])) for row in publications)
    if not isinstance(cap, int) or cap < 1 or count > cap:
        parser.error("Plan exceeds its declared candidate bound")
    results = []
    for publication in publications:
        result = archive.archive_consumed(ROOT, publication, apply=args.apply)
        results.append({"publication_receipt": publication.get("publication_receipt"), **result})
    output = {"schema_version": 1, "mode": "apply" if args.apply else "check",
              "plan": str(plan_path.relative_to(ROOT)), "candidate_count": count,
              "publications": results}
    suffix = ".results.json" if args.apply else ".check.json"
    destination = Path(str(plan_path) + suffix)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"result": str(destination.relative_to(ROOT)), "candidate_count": count,
                      "archived_count": sum(len(row["archived"]) for row in results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
