"""Dry-run all Markdown source labels; optional fingerprint-guarded, idempotent label-only backfill.

Run after the additive option_labels migration. Dry-run also works before that
migration: it reflects the old schema and substitutes [] for the absent column.
Applying requires the exact reviewed dry-run JSON; no answers are ever changed.
"""

import argparse
import asyncio
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from sqlalchemy import inspect, text

from app.core.db import get_engine
from app.services.option_labels import answer_letters, labels_for

FIELDS = ("id", "qid", "bank_group", "bank", "subject_dir", "system", "chapter", "qtype", "stem", "parent_stem",
          "options", "option_labels", "answer", "analysis", "meta", "source_file", "tags", "is_real_exam")
HEADER = re.compile(r"(?m)^### .*?`id:(\d+)`[^\n]*$")
OPTION = re.compile(r"(?m)^- ([A-Z])[.．、][ \t]*([^\r\n]*)[ \t]*$")


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_index(root):
    """Read each source file once, keeping only explicit noncontiguous records."""
    index = {}
    counts = Counter()
    for path in sorted(root.rglob("*.md")):
        counts["files"] += 1
        content = path.read_text(encoding="utf-8-sig")
        headers = list(HEADER.finditer(content))
        for i, header in enumerate(headers):
            end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
            record = content[header.end():end]
            complete_record = content[header.start():end]
            answer = re.search(r"\*\*答案[：:]([^*]+)\*\*", record)
            # Explanations often repeat labelled alternatives. They are not
            # part of the authoritative option block before the answer marker.
            option_block = record[:answer.start()] if answer else record
            pairs = list(OPTION.finditer(option_block))
            if not pairs:
                continue
            labels = [pair[1] for pair in pairs]
            if labels == list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(labels)]):
                continue
            counts["noncontiguous_records"] += 1
            item = {"qid": header[1], "source_file": path.relative_to(root).as_posix(),
                    "stem": record[:pairs[0].start()].strip(), "options": [pair[2] for pair in pairs],
                    "answer": answer[1].strip() if answer else None, "option_labels": labels,
                    "record_sha256": hashlib.sha256(complete_record.encode()).hexdigest(),
                    "source_line": content[:header.start()].count("\n") + 1}
            index.setdefault(header[1], []).append(item)
    return index, dict(counts)


def payload(row):
    result = dict(row)
    for name in ("options", "option_labels", "tags"):
        if isinstance(result.get(name), str):
            result[name] = json.loads(result[name])
    return {field: result.get(field, [] if field == "option_labels" else "") for field in FIELDS}


def assess(row, sources):
    data = payload(row)
    item = {"database_id": data["id"], "qid": data["qid"], "before": data, "before_sha256": digest(data)}
    records = sources.get(str(data["qid"]), [])
    if len(records) != 1:
        return dict(item, status="missing_or_ambiguous_source_qid")
    source = records[0]
    item["source"] = source
    checks = {
        "source_path_matches": data["source_file"].replace("\\", "/") == source["source_file"],
        "stem_matches": norm(data["stem"]) == norm(source["stem"]),
        "ordered_option_texts_match": [norm(v) for v in data["options"]] == [norm(v) for v in source["options"]],
        "answer_matches": norm(data["answer"]) == norm(source["answer"]),
    }
    item["checks"] = checks
    if not all(checks.values()):
        return dict(item, status="source_content_mismatch", skip_reasons=[name for name, ok in checks.items() if not ok])
    try:
        proposed = labels_for(data["options"], source["option_labels"])
    except ValueError as error:
        return dict(item, status="invalid_source_labels", skip_reasons=[str(error)])
    if not answer_letters(data["answer"]) or not answer_letters(data["answer"]) <= set(proposed):
        return dict(item, status="answer_references_missing_source_label")
    if data["option_labels"] == proposed:
        return dict(item, status="already_applied", proposed_labels=proposed)
    if data["option_labels"]:
        return dict(item, status="existing_explicit_labels_conflict", proposed_labels=proposed)
    return dict(item, status="ready", proposed_labels=proposed)


async def run(args):
    root = args.kb_root.resolve()
    if not root.is_dir():
        raise ValueError("kb-root必须是存在的原始Markdown目录")
    sources, counts = source_index(root)
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            has_column = await conn.run_sync(lambda sync: "option_labels" in {c["name"] for c in inspect(sync).get_columns("questions")})
            if not args.apply:
                if conn.dialect.name == "postgresql":
                    await conn.rollback()
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                columns = ", ".join(field if field != "option_labels" or has_column else "'[]' AS option_labels" for field in FIELDS)
                rows = (await conn.execute(text(f"SELECT {columns} FROM questions ORDER BY id"))).mappings().all()
                matches = [assess(row, sources) for row in rows if str(row["qid"]) in sources]
                db_qids = {str(row["qid"]) for row in rows}
                unmatched = sorted(set(sources) - db_qids)
                report = {"schema_version": 1, "mode": "dry_run", "kb_root": str(root),
                          "has_option_labels_column": has_column, "source_scan": counts,
                          "database_questions_scanned": len(rows), "source_qids_missing_in_database": unmatched,
                          "statuses": dict(Counter(item["status"] for item in matches)), "questions": matches,
                          "writes": 0, "answers_changed": 0}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({key: report[key] for key in ("source_scan", "database_questions_scanned", "statuses", "writes", "answers_changed")}))
                return
            if not has_column or args.plan is None:
                raise ValueError("应用前须完成数据库迁移，并传入已审核dry-run --plan文件")
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            if plan.get("mode") != "dry_run":
                raise ValueError("只接受dry-run计划")
            await conn.rollback()
            changed = 0
            async with conn.begin():
                for expected in plan["questions"]:
                    if expected["status"] != "ready":
                        continue
                    lock = " FOR UPDATE" if conn.dialect.name == "postgresql" else ""
                    current = (await conn.execute(text("SELECT " + ", ".join(FIELDS) + " FROM questions WHERE id=:id" + lock),
                                                  {"id": expected["database_id"]})).mappings().one()
                    result = assess(current, sources)
                    if (result.get("source", {}).get("record_sha256") != expected["source"]["record_sha256"]
                            or result.get("proposed_labels") != expected["proposed_labels"]):
                        raise ValueError("原始标签源记录已变化，整批回滚：" + str(expected["qid"]))
                    if result["status"] == "already_applied":
                        baseline = dict(result["before"], option_labels=expected["before"]["option_labels"])
                        if digest(baseline) != expected["before_sha256"]:
                            raise ValueError("已回填题目其他内容变化，拒绝忽略：" + result["qid"])
                        continue
                    if (result["status"] != "ready" or result["before_sha256"] != expected["before_sha256"]
                            or result["source"]["record_sha256"] != expected["source"]["record_sha256"]
                            or result["proposed_labels"] != expected["proposed_labels"]):
                        raise ValueError("题目或源记录发生变化，整批回滚：" + str(expected["qid"]))
                    encoded = json.dumps(result["proposed_labels"])
                    assignment = "CAST(:labels AS jsonb)" if conn.dialect.name == "postgresql" else ":labels"
                    await conn.execute(text("UPDATE questions SET option_labels=" + assignment + " WHERE id=:id"),
                                       {"labels": encoded, "id": expected["database_id"]})
                    changed += 1
            print(json.dumps({"labels_updated": changed, "answers_changed": 0}))
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", type=Path, default=Path(__file__).resolve().parents[2] / "kb")
    parser.add_argument("--output", type=Path, default=Path("output/option-label-backfill-dry-run.json"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan", type=Path)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
