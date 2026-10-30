import hashlib
import json
from functools import lru_cache
from collections import defaultdict
from pathlib import Path
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md, md
from app.models import Card, ContentCitation, EditorialBatch, EditorialExecution, EditorialReview, Question
from app.services.card_merges import redirects, resolve
from app.schemas.editorial import ReviewDecisionIn, ReviewQueue

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "editorial_review.json"
QUESTION_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "question_evidence_review_queue.json"
CLASSES = {
    "text_exact_all_non_id_fields": ("exact", "完整字段完全相同；仍需核对学习进度、题目关联和媒体，不能直接删卡。"),
    "same_subject_same_term_candidate": ("titles", "仅学科和标题相同。正文可能互补、冲突或指向不同考点，请逐段比较，默认保留。"),
    "same_term_collision_not_semantic_duplicate": ("titles", "同名但不同考点，不能按标题合并。"),
    "cross_subject_same_term_link_candidate": ("cross_subject", "按正文确定实际主学科；同一知识点先修正归类后合并，不同知识重点保留独立卡片并互引。不能只凭标题操作。"),
    "semantic_overlap_representative_not_record_duplicate": ("overlap", "存在部分机制或知识点重叠；请保留各卡独有内容，审核分拆、交叉引用或提炼公共解释的方案。"),
}


@lru_cache(maxsize=1)
def catalog():
    raw = DATA_PATH.read_bytes().replace(b"\r\n", b"\n")
    data = json.loads(raw)
    dataset = hashlib.sha256(raw).hexdigest()[:24]
    sources = {s["id"]: s for s in data["sources"]}
    items = {}
    for group in data["groups"]:
        category, guidance = CLASSES[group["match_class"]]
        items[group["group_id"]] = dict(
            id=group["group_id"], category=category, title=" / ".join(group["terms"]),
            subjects=group["subjects"], card_ids=group["member_ids"], cards=group["original_cards"],
            guidance=guidance, evidence=group["evidence"], proposal="",
            sources=[dict(title=url, url=url) for url in group["source_urls"]],
            differing_fields=group["differing_fields"], requires_media_review=group["requires_media_review"],
        )
    for sample in data["mechanism_examples"]:
        items[sample["sample_id"]] = dict(
            id=sample["sample_id"], category="mechanisms", title=sample["proposed_term"],
            subjects=sorted({c["subject"] for c in sample["original_cards"]}),
            card_ids=sample["original_card_ids"], cards=sample["original_cards"],
            guidance="中文机制解释草稿，仅供审核；不覆盖原卡，不代表原卡其余结论已核实。发布前仍需按教材核对。",
            evidence=sample["preserve_note"], proposal=sample["proposed_text"],
            sources=[sources[s] for s in sample["source_ids"]], differing_fields=[], requires_media_review=False,
        )
    for finding in data["note_findings"]:
        items[finding["finding_id"]] = dict(
            id=finding["finding_id"], category="chapters", title=finding["title"], subjects=[finding["subject"]],
            card_ids=[], cards=[], chapter_id=finding["chapter_id"],
            guidance="章节归类或段落结构审核：只处理被标记的段落，不整体搬迁章节，不自动改写医学内容。",
            evidence=finding["proposed_action"], proposal="", original_html=md(finding["original_point"]),
            source_file=finding["source_file"], line=finding["line_1_based"],
            sources=[dict(title=url, url=url) for url in finding["source_urls"]],
            differing_fields=[], requires_media_review=False,
        )
    return dataset, data["audit_date"], items


@lru_cache(maxsize=1)
def question_catalog():
    data = json.loads(QUESTION_DATA_PATH.read_bytes())
    items = {item["id"]: item for item in data["items"]}
    if len(items) != len(data["items"]):
        raise ValueError("题目答案证据队列包含重复项目ID")
    items = link_expanded_question_items(items)
    return data["dataset_id"], data["audit_date"], items


def link_expanded_question_items(items):
    """Derive presentation links without changing catalog IDs or stored review rows."""
    linked = {ident: dict(item) for ident, item in items.items()}
    candidates = defaultdict(list)
    for item in linked.values():
        if item["id"].startswith("QA03R-"):
            for gid in item.get("related_ledger_groups", []):
                candidates[gid].append(item)
    for ident, legacy in linked.items():
        if not ident.startswith("QA03-"):
            continue
        member_ids = set(legacy.get("question_ids", []))
        if not member_ids:
            continue
        complete = [item for item in candidates.get(legacy.get("group_id"), [])
                    if member_ids <= set(item.get("question_ids", []))]
        if not complete:
            continue
        expanded = min(complete, key=lambda item: (len(item["question_ids"]), item["id"]))
        legacy["superseded_by"] = expanded["id"]
        expanded["related_item_ids"] = sorted({*expanded.get("related_item_ids", []), ident})
        if legacy.get("review", {}).get("status") == "pending_evidence":
            expanded["evidence_pending"] = True
    return linked


def decision_out(row: EditorialReview | None):
    return dict(status=row.status if row else "pending", note=row.note if row else "",
                version=row.version if row else 0, updated_by=row.updated_by if row else None,
                updated_at=row.updated_at.isoformat() if row and row.updated_at else None)


def execution_out(row: EditorialExecution | None, review: EditorialReview | None):
    if row is None:
        return None
    return dict(status=row.status, description=row.description, affected_ids=row.affected_ids,
                batch_id=row.batch_id, created_at=row.created_at.isoformat(),
                needs_recheck=row.review_version != (review.version if review else 0))


async def decisions(session: AsyncSession, dataset: str):
    rows = (await session.execute(
        select(EditorialReview).where(EditorialReview.key.startswith(dataset + ":"))
    )).scalars().all()
    return {r.key.split(":", 1)[1]: r for r in rows}


def review_queue(review: EditorialReview | None, execution: EditorialExecution | None, item=None) -> ReviewQueue:
    finished = {"merged", "linked", "revised", "renamed", "kept", "unchanged"}
    if item and item.get("category") == "question_evidence":
        catalog_status = item.get("review", {}).get("status")
        if (
            item.get("evidence_pending")
            or catalog_status in {"unreviewed", "pending_evidence", "pending_review"}
            or (review is not None and review.status == "needs_revision")
        ):
            # A historical execution at review version 0 must not hide a card
            # whose catalog still says it has not been reviewed or has evidence
            # outstanding. Resolve these states before checking execution.
            return "needs_review"
        if catalog_status == "excluded" and review is None and execution is None:
            # A catalog-side adjudication has already excluded this resolved item.
            # Do not reopen it as pending merely because no human decision row exists.
            return "completed"
    pending_work = (
        execution is None or execution.status not in finished
        or execution.review_version != (review.version if review else 0)
    )
    if not pending_work:
        return "completed"
    return "needs_review" if review is None or review.status == "pending" else "waiting_execution"


async def list_items(
    session: AsyncSession, category: str, status: str, query: str, offset: int, size: int,
    queue: ReviewQueue = "all",
):
    dataset, date, editorial_items = catalog()
    question_dataset, question_date, question_items = question_catalog()
    items = editorial_items | question_items
    reviews: dict[str, EditorialReview] = {}
    executions: dict[str, EditorialExecution] = {}
    for item_dataset in {dataset, question_dataset}:
        reviews.update(await decisions(session, item_dataset))
        executions.update({r.key.split(":", 1)[1]: r for r in (await session.scalars(
            select(EditorialExecution).where(EditorialExecution.key.startswith(item_dataset + ":"))
        )).all()})
    # Superseded IDs remain readable as history, but have one active expanded task.
    active_items = {ident: item for ident, item in items.items() if not item.get("superseded_by")}
    queues = {ident: review_queue(reviews.get(ident), executions.get(ident), item)
              for ident, item in active_items.items()}
    queue_counts = {key: sum(value == key for value in queues.values())
                    for key in ("needs_review", "waiting_execution", "completed")}
    queue_counts["all"] = len(active_items)
    needle = query.strip().casefold()
    scoped = [
        i for i in active_items.values()
        if (queue == "all" or queues[i["id"]] == queue)
        and (not status or decision_out(reviews.get(i["id"]))["status"] == status)
        and (not needle or needle in " ".join([i["id"], i["title"], *i["subjects"], *map(str, i["card_ids"]),
                                                *map(str, i.get("question_ids", [])), *i.get("qids", [])]).casefold())
    ]
    counts: dict[str, int] = {}
    for item in scoped:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    filtered = [i for i in scoped if not category or i["category"] == category]
    return dict(dataset_id=dataset, audit_date=date, counts=counts, queue_counts=queue_counts,
                total=len(filtered), offset=offset,
                items=[dict(id=i["id"], category=i["category"], title=i["title"], subjects=i["subjects"],
                            card_ids=i["card_ids"], question_ids=i.get("question_ids", []),
                            decision=decision_out(reviews.get(i["id"])),
                            work_queue=queues[i["id"]])
                            | {"execution": execution_out(executions.get(i["id"]), reviews.get(i["id"]))}
                       for i in filtered[offset:offset + size]])


def item_or_404(item_id: str):
    dataset, date, items = catalog()
    if item_id in items:
        return dataset, date, items[item_id]
    question_dataset, question_date, question_items = question_catalog()
    if item_id in question_items:
        return question_dataset, question_date, question_items[item_id]
    raise HTTPException(404, "审核项目不存在")


CARD_FIELDS = ("id", "subject", "part", "section", "term", "hint", "body", "source_file")


def card_out(fields):
    return {**fields, "body_html": card_md(fields["body"]), "term_html": md(fields["term"])}


ANSWER_ADJUDICATION_FIELDS = ("id", "qid", "qtype", "stem", "parent_stem", "options", "option_labels", "answer")


def answer_adjudication_for_question(question, execution, batch, citations):
    """Expose a textbook verdict only while its explicit evidence still matches."""
    if (not execution or execution.get("status") != "revised" or execution.get("needs_recheck")
            or question.id not in execution.get("affected_ids", []) or batch is None
            or batch.status != "committed" or batch.id != execution.get("batch_id")):
        return None
    after = batch.after if isinstance(batch.after, dict) else {}
    metadata = after.get("answer_adjudication")
    if (not isinstance(metadata, dict) or metadata.get("schema_version") != 1
            or metadata.get("method") != "textbook" or metadata.get("plan_hash") != batch.plan_hash):
        return None
    entries = metadata.get("questions")
    entry = entries.get(str(question.id)) if isinstance(entries, dict) else None
    if not isinstance(entry, dict) or entry.get("answer") != question.answer:
        return None
    payload = {key: getattr(question, key) for key in ANSWER_ADJUDICATION_FIELDS}
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode("utf-8")).hexdigest()
    citation_ids = entry.get("citation_ids")
    if (entry.get("payload_sha256") != fingerprint or not isinstance(entry.get("answer_text"), str)
            or not entry["answer_text"].strip() or not isinstance(citation_ids, list) or not citation_ids
            or any(type(ident) is not int or ident <= 0 for ident in citation_ids)
            or len(citation_ids) != len(set(citation_ids))):
        return None
    current = {citation["id"]: citation for citation in citations}
    if any(current.get(ident, {}).get("status") != "verified" for ident in citation_ids):
        return None
    return {"status": "textbook_verified", "batch_id": batch.id, "answer_text": entry["answer_text"],
            "citation_ids": citation_ids,
            "historical_official_answer_verified": metadata.get("historical_official_answer_verified") is True}


async def detail(session: AsyncSession, item_id: str):
    dataset, date, item = item_or_404(item_id)
    live = {c.id: c for c in (await session.execute(
        select(Card).where(Card.id.in_(item["card_ids"]))
    )).scalars()} if item["card_ids"] else {}
    cards = []
    mapping = await redirects(session)
    for original in item.get("cards", []):
        current = live.get(original["id"])
        current_fields = {k: getattr(current, k) for k in CARD_FIELDS} if current else None
        cards.append(dict(snapshot=card_out(original), current=card_out(current_fields) if current_fields else None,
                          changed=current_fields != {k: original[k] for k in CARD_FIELDS},
                          merged_into=resolve(mapping, original["id"]) if original["id"] in mapping else None))
    row = await session.get(EditorialReview, dataset + ":" + item_id)
    execution_row = await session.get(EditorialExecution, dataset + ":" + item_id)
    execution = execution_out(execution_row, row)
    executed = bool(execution and not execution["needs_recheck"]
                    and execution["status"] in ("merged", "linked", "revised", "renamed"))
    adjudication_batch = (await session.get(EditorialBatch, execution["batch_id"])
                          if executed and execution["status"] == "revised" else None)
    related_reviews = []
    prior_question_ids = set()
    for previous_id in item.get("related_item_ids", []):
        previous_dataset, _, previous = item_or_404(previous_id)
        previous_review = await session.get(EditorialReview, previous_dataset + ":" + previous_id)
        previous_execution = await session.get(EditorialExecution, previous_dataset + ":" + previous_id)
        prior_question_ids.update(previous.get("question_ids", []))
        related_reviews.append({"id": previous_id, "title": previous["title"],
            "question_ids": previous.get("question_ids", []), "qids": previous.get("qids", []),
            "decision": decision_out(previous_review), "execution": execution_out(previous_execution, previous_review),
            "evidence": previous.get("evidence", ""), "source_review_status": previous.get("review", {}).get("status")})
    question_cards = []
    question_ids = item.get("question_ids", [])
    if question_ids:
        questions = {q.id: q for q in (await session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )).scalars()}
        citation_rows = (await session.execute(select(ContentCitation).where(
            ContentCitation.target_type == "question", ContentCitation.target_id.in_(question_ids)
        ).order_by(ContentCitation.target_id, ContentCitation.id))).scalars().all()
        citations_by_id: dict[int, list[dict]] = {}
        for citation in citation_rows:
            citations_by_id.setdefault(citation.target_id, []).append({
                "id": citation.id, "source_key": citation.source_key, "chapter": citation.chapter,
                "section": citation.section, "page_start": citation.page_start, "page_end": citation.page_end,
                "note": citation.note, "status": citation.status,
            })
        for qid, database_id in zip(item.get("qids", []), question_ids):
            q = questions.get(database_id)
            if q is None:
                question_cards.append({
                    "id": database_id, "qid": qid, "qtype": "", "subject_dir": "", "system": "",
                    "stem": "题库中暂未找到此题，请核对题目编号。", "stem_html": "题库中暂未找到此题，请核对题目编号。",
                    "parent_stem": "", "parent_stem_html": "", "options": [], "option_labels": [],
                    "options_html": [], "answer": "", "analysis": "", "analysis_html": "",
                    "source_file": "", "citations": [], "missing": True,
                })
                continue
            options = list(q.options or [])
            question_cards.append({
                "id": q.id, "qid": q.qid, "qtype": q.qtype, "subject_dir": q.subject_dir,
                "system": q.system, "stem": q.stem, "stem_html": md(q.stem),
                "parent_stem": q.parent_stem, "parent_stem_html": md(q.parent_stem) if q.parent_stem else "",
                "options": options, "option_labels": list(q.option_labels or []),
                "options_html": [md(option) for option in options], "answer": q.answer,
                "analysis": q.analysis, "analysis_html": md(q.analysis), "source_file": q.source_file,
                "citations": citations_by_id.get(q.id, []), "missing": False,
                "answer_adjudication": answer_adjudication_for_question(
                    q, execution, adjudication_batch, citations_by_id.get(q.id, [])),
            })
    return {**{k: v for k, v in item.items() if k != "cards"}, "cards": cards,
            "dataset_id": dataset, "audit_date": date, "proposal_html": card_md(item["proposal"]),
            "decision": decision_out(row), "execution": execution, "executed": executed,
            "work_queue": review_queue(row, execution_row, item), "questions": question_cards,
            "related_reviews": related_reviews,
            "requires_evidence_review": bool(item.get("category") == "question_evidence" and (
                item.get("evidence_pending") or item.get("review", {}).get("status") == "pending_evidence"
                or (row is not None and row.status == "needs_revision"))),
            "additional_question_ids": sorted(set(question_ids) - prior_question_ids) if related_reviews else []}


async def save_decision(session: AsyncSession, admin_id: int, item_id: str, body: ReviewDecisionIn):
    dataset, _, item = item_or_404(item_id)
    if item.get("superseded_by"):
        raise HTTPException(409, "此题组已纳入完整扩展组，请刷新并在扩展组补充意见；原审核意见已保留。")
    key = dataset + ":" + item_id
    if body.expected_version == 0:
        session.add(EditorialReview(key=key, status=body.status, note=body.note, updated_by=admin_id, version=1))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(409, "审核意见已被其他管理员更新，请刷新后重试") from None
    else:
        result = cast(CursorResult, await session.execute(
            update(EditorialReview).where(EditorialReview.key == key, EditorialReview.version == body.expected_version)
            .values(status=body.status, note=body.note, updated_by=admin_id, version=body.expected_version + 1)
        ))
        if result.rowcount != 1:
            await session.rollback()
            raise HTTPException(409, "审核意见已被其他管理员更新，请刷新后重试")
        await session.commit()
    row = await session.get(EditorialReview, key, populate_existing=True)
    return decision_out(row)
