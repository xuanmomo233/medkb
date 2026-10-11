import json
import re
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

_QREF = re.compile(r"Q(\d+)")
_PAGE = re.compile(r"page_(\d+)")
_TAG_SPLIT = re.compile(r"[,，、;；]")

LIMITS = {
    "questions": {"qid": 32, "bank_group": 64, "bank": 64, "subject_dir": 32, "system": 64,
                  "chapter": 200, "qtype": 16, "answer": 32, "source_file": 255},
    "cards": {"subject": 32, "part": 64, "section": 128, "term": 200, "source_file": 255},
    "chapters": {"kind": 16, "subject": 32, "title": 200, "source_file": 255},
}

QUESTION_COLS = ["id", "qid", "chapter", "subjdir", "system", "bank", "bankgrp", "qtype", "stem",
                 "options", "answer", "analysis", "parent", "meta", "srcfile", "tags"]
CARD_COLS = ["id", "subj_real", "part", "section", "term", "hint", "body", "qids", "srcfile"]
CHAPTER_COLS = ["id", "subj", "title", "kind", "content", "srcfile"]


def s(v: Any) -> str:
    return "" if v is None else str(v)


def parse_options(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [s(x) for x in raw]
    t = s(raw).strip()
    if not t:
        return []
    try:
        v = json.loads(t)
    except (ValueError, TypeError):
        return []
    return [s(x) for x in v] if isinstance(v, list) else []


def parse_tags(raw: Any) -> list[str]:
    out: list[str] = []
    for t in _TAG_SPLIT.split(s(raw)):
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def extract_pages(content: str) -> list[int]:
    return sorted({int(x) for x in _PAGE.findall(content or "")})


def extract_qrefs(qids: Any) -> list[str]:
    """'[Q123] [Q456]' -> ['123', '456']（保序，不去重）"""
    return _QREF.findall(s(qids))


def norm_qid(qid: Any) -> str:
    return s(qid).strip().lstrip("Qq")


def _clip(table: str, row: dict, stats: dict) -> dict:
    for k, n in LIMITS[table].items():
        v = row.get(k)
        if isinstance(v, str) and len(v) > n:
            row[k] = v[:n]
            stats["truncated"][f"{table}.{k}"] = stats["truncated"].get(f"{table}.{k}", 0) + 1
    return row


def map_question(r: dict) -> dict:
    src = s(r.get("srcfile"))
    return {
        "id": int(r["id"]), "qid": s(r.get("qid")).strip(),
        "bank_group": s(r.get("bankgrp")), "bank": s(r.get("bank")),
        "subject_dir": s(r.get("subjdir")), "system": s(r.get("system")),
        "chapter": s(r.get("chapter")), "qtype": s(r.get("qtype")) or "单选",
        "stem": s(r.get("stem")), "options": parse_options(r.get("options")),
        "answer": s(r.get("answer")), "analysis": s(r.get("analysis")),
        "parent_stem": s(r.get("parent")), "meta": s(r.get("meta")),
        "source_file": src, "tags": parse_tags(r.get("tags")),
        "is_real_exam": "真题" in src,
    }


def map_card(r: dict) -> dict:
    return {
        "id": int(r["id"]), "subject": s(r.get("subj_real")), "part": s(r.get("part")),
        "section": s(r.get("section")), "term": s(r.get("term")), "hint": s(r.get("hint")),
        "body": s(r.get("body")), "source_file": s(r.get("srcfile")),
    }


def map_chapter(r: dict) -> dict:
    content = s(r.get("content"))
    return {
        "id": int(r["id"]), "kind": "mindmap" if s(r.get("kind")) == "mm" else "note",
        "subject": s(r.get("subj")), "title": s(r.get("title")), "content_md": content,
        "source_file": s(r.get("srcfile")), "pages": extract_pages(content),
    }


def new_stats() -> dict:
    return {"questions": 0, "questions_dup_qid": 0, "questions_empty_options": 0,
            "questions_bad_options": 0, "questions_tags": 0, "questions_real_exam": 0,
            "cards": 0, "card_refs": 0, "card_refs_matched": 0, "card_refs_unmatched": 0,
            "card_refs_dup": 0, "cards_no_refs": 0, "card_questions": 0,
            "chapters": 0, "chapters_mindmap": 0, "chapters_with_pages": 0,
            "truncated": {}, "unmatched_samples": []}


def open_legacy(url: str) -> Engine:
    return create_engine(url)


def legacy_table_names(eng: Engine) -> dict[str, str]:
    names = set(inspect(eng).get_table_names())
    card_t = "kp_items_v2" if "kp_items_v2" in names else "kp_items"
    for t in ("questions", card_t, "chapters"):
        if t not in names:
            raise RuntimeError(f"旧库缺少表 {t}")
    return {"questions": "questions", "cards": card_t, "chapters": "chapters"}


def iter_legacy(eng: Engine, table: str, cols: list[str], batch: int) -> Iterator[list[dict]]:
    have = {c["name"] for c in inspect(eng).get_columns(table)}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in cols)
    with eng.connect() as conn:
        res = conn.execution_options(stream_results=True).execute(
            text(f"SELECT {sel} FROM {table} ORDER BY id"))
        while True:
            rows = res.fetchmany(batch)
            if not rows:
                return
            yield [dict(r._mapping) for r in rows]


def legacy_counts(eng: Engine) -> dict[str, int]:
    t = legacy_table_names(eng)
    with eng.connect() as conn:
        return {k: conn.execute(text(f"SELECT COUNT(*) FROM {v}")).scalar_one()
                for k, v in t.items()}


def build_card_links(card_id: int, qids_text: Any, qmap: dict[str, int], stats: dict) -> list[dict]:
    refs = extract_qrefs(qids_text)
    if not refs:
        stats["cards_no_refs"] += 1
    seen: set[int] = set()
    out = []
    for ref in refs:
        stats["card_refs"] += 1
        qid = qmap.get(ref)
        if qid is None:
            stats["card_refs_unmatched"] += 1
            if len(stats["unmatched_samples"]) < 20:
                stats["unmatched_samples"].append(f"card {card_id}: Q{ref}")
        elif qid in seen:
            stats["card_refs_dup"] += 1
        else:
            seen.add(qid)
            stats["card_refs_matched"] += 1
            out.append({"card_id": card_id, "question_id": qid})
    return out


def prepare_questions(rows: list[dict], seen_qids: set[str], stats: dict) -> list[dict]:
    out = []
    for r in rows:
        m = map_question(r)
        if not m["qid"] or m["qid"] in seen_qids:
            stats["questions_dup_qid"] += 1
            continue
        seen_qids.add(m["qid"])
        raw = r.get("options")
        if not m["options"]:
            stats["questions_empty_options"] += 1
            if s(raw).strip() and s(raw).strip() not in ("[]",):
                stats["questions_bad_options"] += 1
        stats["questions_tags"] += len(m["tags"])
        stats["questions_real_exam"] += m["is_real_exam"]
        stats["questions"] += 1
        out.append(_clip("questions", m, stats))
    return out
