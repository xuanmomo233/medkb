"""Read-only audit of same-stem questions with differing answer meanings.

The scan does not update production data. It groups by question type, shared
case stem, and question stem after NFKC/whitespace normalization. Letter answers
are translated through each record's own option list before comparison, so
option order changes do not create false answer conflicts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session
from app.models import Question


ANSWER_LETTERS = "ABCDEFGHIJ"
ANSWER_TOKEN = re.compile(r"(?<![A-Z])[A-J](?![A-Z])")
OPTION_PREFIX = re.compile(r"^\s*[A-JＡ-Ｊ]\s*[.、．)）:：]\s*")
ANSWER_SEPARATORS = re.compile(r"[\s,，、和及与&/／;；|｜()（）\[\]【】.．:：]+")


def norm(value: object) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def options_list(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    return [str(item or "") for item in value]


def analysis_preview(value: object, limit: int = 500) -> str:
    """Expose enough source context to catch generic-stem false positives."""
    text = str(value or "")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def answer_meaning(answer: object, options: list[str]) -> tuple[str | None, str]:
    raw = unicodedata.normalize("NFKC", str(answer or "")).upper().strip()
    if not raw:
        return None, "empty"
    raw = re.sub(r"^(?:正确答案|答案|ANSWER)\s*[:：]?\s*", "", raw)

    # Only interpret a value as option letters when nothing except letters and
    # conventional answer separators remains after removing the tokens.
    compact = ANSWER_SEPARATORS.sub("", raw)
    letters = list(compact) if re.fullmatch(r"[A-J]{1,10}", compact) else ANSWER_TOKEN.findall(raw)
    residue = "" if re.fullmatch(r"[A-J]{1,10}", compact) else ANSWER_TOKEN.sub("", raw)
    if letters and not ANSWER_SEPARATORS.sub("", residue):
        indices = sorted({ANSWER_LETTERS.index(letter) for letter in letters})
        if options and all(index < len(options) for index in indices):
            meanings = tuple(sorted(norm(OPTION_PREFIX.sub("", options[index])) for index in indices))
            if all(meanings):
                return json.dumps(meanings, ensure_ascii=False), "mapped"
        return None, "unmapped_letters"

    direct = norm(raw)
    matching = [norm(OPTION_PREFIX.sub("", option)) for option in options]
    if direct and direct in matching:
        return json.dumps((direct,), ensure_ascii=False), "mapped_text"
    return None, "unparsed"


async def scan() -> dict:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    async for session in get_session():
        result = await session.execute(
            select(
                Question.id,
                Question.qid,
                Question.qtype,
                Question.parent_stem,
                Question.stem,
                Question.options,
                Question.answer,
                Question.bank,
                Question.bank_group,
                Question.subject_dir,
                Question.system,
                Question.chapter,
                Question.source_file,
                Question.analysis,
            ).order_by(Question.id)
        )
        for row in result:
            stem_key = (norm(row.qtype), norm(row.parent_stem), norm(row.stem))
            if not stem_key[2]:
                continue
            options = options_list(row.options)
            meaning, parse_status = answer_meaning(row.answer, options)
            option_meanings = [norm(OPTION_PREFIX.sub("", item)) for item in options]
            groups[stem_key].append(
                {
                    "id": row.id,
                    "qid": row.qid,
                    "answer": row.answer or "",
                    "meaning": meaning,
                    "parse_status": parse_status,
                    "option_meanings": option_meanings,
                    "bank": row.bank or "",
                    "bank_group": row.bank_group or "",
                    "subject_dir": row.subject_dir or "",
                    "system": row.system or "",
                    "chapter": row.chapter or "",
                    "source_file": row.source_file or "",
                    "analysis_preview": analysis_preview(row.analysis),
                    "stem": row.stem or "",
                }
            )
        break

    conflicts = []
    for key, rows in groups.items():
        if len(rows) < 2:
            continue
        parseable = [row for row in rows if row["meaning"] is not None]
        meanings = {row["meaning"] for row in parseable}
        if len(meanings) < 2:
            continue
        options_sets = {tuple(sorted(row["option_meanings"])) for row in rows}
        conflicts.append(
            {
                "qtype": key[0],
                "parent_stem": key[1],
                "stem": key[2],
                "question_count": len(rows),
                "parseable_count": len(parseable),
                "unparsed_count": len(rows) - len(parseable),
                "same_option_texts": len(options_sets) == 1,
                "rows": rows,
            }
        )

    conflicts.sort(key=lambda item: (not item["same_option_texts"], -item["question_count"], item["stem"]))
    unparsed_groups = [
        rows
        for rows in groups.values()
        if len(rows) > 1 and len({row["answer"] for row in rows}) > 1
        and any(row["meaning"] is None for row in rows)
    ]
    unparsed_questions = sum(
        1
        for rows in groups.values()
        if len(rows) > 1 and len({row["answer"] for row in rows}) > 1
        for row in rows
        if row["meaning"] is None
    )
    return {
        "questions_scanned": sum(map(len, groups.values())),
        "same_stem_groups": sum(1 for rows in groups.values() if len(rows) > 1),
        "conflict_group_count": len(conflicts),
        "conflict_question_count": sum(item["question_count"] for item in conflicts),
        "same_option_text_conflict_groups": sum(item["same_option_texts"] for item in conflicts),
        "unparsed_multi_answer_group_count": len(unparsed_groups),
        "unparsed_question_count": unparsed_questions,
        "conflicts": conflicts,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the complete JSON report to this path")
    parser.add_argument("--sample", type=int, default=20, help="number of sample groups in stdout")
    parser.add_argument("--only-same-options", action="store_true", help="show only conflicts with identical option text sets")
    parser.add_argument("--compact", action="store_true", help="omit full question rows and emit a compact manual review queue")
    args = parser.parse_args()
    report = await scan()
    summary = {key: value for key, value in report.items() if key != "conflicts"}
    samples = [item for item in report["conflicts"] if item["same_option_texts"]] if args.only_same_options else report["conflicts"]
    summary["samples"] = samples[: max(0, args.sample)]
    if args.compact:
        summary["samples"] = [
            {
                "qtype": item["qtype"],
                "stem": next((row["stem"] for row in item["rows"] if row["stem"]), ""),
                "options": next((row["option_meanings"] for row in item["rows"] if row["option_meanings"]), []),
                "rows": [
                    {
                        key: row[key]
                        for key in (
                            "id",
                            "qid",
                            "answer",
                            "meaning",
                            "bank",
                            "bank_group",
                            "subject_dir",
                            "system",
                            "chapter",
                            "source_file",
                            "analysis_preview",
                        )
                    }
                    for row in item["rows"]
                ],
            }
            for item in summary["samples"]
        ]
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["full_report"] = str(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
