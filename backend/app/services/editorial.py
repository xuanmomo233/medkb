import hashlib
import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md, md
from app.models import Card, EditorialReview
from app.schemas.editorial import ReviewDecisionIn

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "editorial_review.json"
CLASSES = {
    "text_exact_all_non_id_fields": ("exact", "完整字段完全相同；仍需核对学习进度、题目关联和媒体，不能直接删卡。"),
    "same_subject_same_term_candidate": ("titles", "仅学科和标题相同。正文可能互补、冲突或指向不同考点，请逐段比较，默认保留。"),
    "same_term_collision_not_semantic_duplicate": ("titles", "同名但不同考点，不能按标题合并。"),
    "cross_subject_same_term_link_candidate": ("cross_subject", "跨学科同名仅作关联候选，不应将不同学科的卡片合并。"),
    "semantic_overlap_representative_not_record_duplicate": ("overlap", "存在部分机制或知识点重叠；请保留各卡独有内容，审核分拆、交叉引用或提炼公共解释的方案。"),
}


@lru_cache(maxsize=1)
def catalog():
    raw = DATA_PATH.read_bytes()
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


def decision_out(row: EditorialReview | None):
    return dict(status=row.status if row else "pending", note=row.note if row else "",
                version=row.version if row else 0, updated_by=row.updated_by if row else None,
                updated_at=row.updated_at.isoformat() if row and row.updated_at else None)


async def decisions(session: AsyncSession, dataset: str):
    rows = (await session.execute(
        select(EditorialReview).where(EditorialReview.key.startswith(dataset + ":"))
    )).scalars().all()
    return {r.key.split(":", 1)[1]: r for r in rows}


async def list_items(session: AsyncSession, category: str, status: str, query: str, offset: int, size: int):
    dataset, date, items = catalog()
    reviews = await decisions(session, dataset)
    counts = {}
    for item in items.values():
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    needle = query.strip().casefold()
    filtered = [
        i for i in items.values()
        if (not category or i["category"] == category)
        and (not status or decision_out(reviews.get(i["id"]))["status"] == status)
        and (not needle or needle in " ".join([i["id"], i["title"], *i["subjects"], *map(str, i["card_ids"])]).casefold())
    ]
    return dict(dataset_id=dataset, audit_date=date, counts=counts, total=len(filtered), offset=offset,
                items=[dict(id=i["id"], category=i["category"], title=i["title"], subjects=i["subjects"],
                            card_ids=i["card_ids"], decision=decision_out(reviews.get(i["id"])))
                       for i in filtered[offset:offset + size]])


def item_or_404(item_id: str):
    dataset, date, items = catalog()
    if item_id not in items:
        raise HTTPException(404, "审核项目不存在")
    return dataset, date, items[item_id]


CARD_FIELDS = ("id", "subject", "part", "section", "term", "hint", "body", "source_file")


def card_out(fields):
    return {**fields, "body_html": card_md(fields["body"]), "term_html": md(fields["term"])}


async def detail(session: AsyncSession, item_id: str):
    dataset, date, item = item_or_404(item_id)
    live = {c.id: c for c in (await session.execute(
        select(Card).where(Card.id.in_(item["card_ids"]))
    )).scalars()} if item["card_ids"] else {}
    cards = []
    for original in item["cards"]:
        current = live.get(original["id"])
        current_fields = {k: getattr(current, k) for k in CARD_FIELDS} if current else None
        cards.append(dict(snapshot=card_out(original), current=card_out(current_fields) if current_fields else None,
                          changed=current_fields != {k: original[k] for k in CARD_FIELDS}))
    row = await session.get(EditorialReview, dataset + ":" + item_id)
    return {**{k: v for k, v in item.items() if k != "cards"}, "cards": cards,
            "dataset_id": dataset, "audit_date": date, "proposal_html": card_md(item["proposal"]),
            "decision": decision_out(row), "executed": False}


async def save_decision(session: AsyncSession, admin_id: int, item_id: str, body: ReviewDecisionIn):
    dataset, _, _ = item_or_404(item_id)
    key = dataset + ":" + item_id
    if body.expected_version == 0:
        session.add(EditorialReview(key=key, status=body.status, note=body.note, updated_by=admin_id, version=1))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(409, "审核意见已被其他管理员更新，请刷新后重试") from None
    else:
        result = await session.execute(
            update(EditorialReview).where(EditorialReview.key == key, EditorialReview.version == body.expected_version)
            .values(status=body.status, note=body.note, updated_by=admin_id, version=body.expected_version + 1)
        )
        if result.rowcount != 1:
            await session.rollback()
            raise HTTPException(409, "审核意见已被其他管理员更新，请刷新后重试")
        await session.commit()
    row = await session.get(EditorialReview, key, populate_existing=True)
    return decision_out(row)
