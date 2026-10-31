from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Chapter, ContentCitation, Question, TextbookSource

TARGET_MODELS = {"chapter": Chapter, "question": Question, "card": Card}

DEFAULT_TEXTBOOKS = (
    {"key": "rjws-physiology-10", "title": "生理学", "subject": "生理学"},
    {"key": "rjws-biochemistry-10", "title": "生物化学与分子生物学", "subject": "生物化学"},
    {"key": "rjws-pathology-10", "title": "病理学", "subject": "病理学"},
    {"key": "rjws-pathophysiology-10", "title": "病理生理学", "subject": "病理生理学"},
    {"key": "rjws-diagnostics-10", "title": "诊断学", "subject": "诊断学"},
    {"key": "rjws-internal-medicine-10", "title": "内科学", "subject": "内科学"},
    {"key": "rjws-surgery-10", "title": "外科学", "subject": "外科学"},
    {"key": "rjws-pediatrics-10", "title": "儿科学", "subject": "儿科学"},
    {"key": "rjws-dermatology-venereology-10", "title": "皮肤性病学", "subject": "皮肤性病学"},
    {"key": "rjws-parasitology-10", "title": "人体寄生虫学", "subject": "人体寄生虫学"},
    {"key": "rjws-pharmacology-10", "title": "药理学", "subject": "药理学"},
    {"key": "rjws-obstetrics-gynecology-10", "title": "妇产科学", "subject": "妇产科学"},
    {"key": "rjws-histology-embryology-10", "title": "组织学与胚胎学", "subject": "组织学与胚胎学"},
)


async def seed_textbooks(session: AsyncSession) -> int:
    existing = set((await session.execute(select(TextbookSource.key))).scalars())
    rows = [
        TextbookSource(
            **item, publisher="人民卫生出版社", edition="第十版", active=True,
        )
        for item in DEFAULT_TEXTBOOKS if item["key"] not in existing
    ]
    session.add_all(rows)
    if rows:
        await session.commit()
    return len(rows)


async def list_sources(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        select(TextbookSource).where(TextbookSource.active.is_(True))
        .order_by(TextbookSource.subject, TextbookSource.title)
    )).scalars().all()
    return [
        {"key": row.key, "title": row.title, "subject": row.subject,
         "publisher": row.publisher, "edition": row.edition}
        for row in rows
    ]


def _out(citation: ContentCitation, source: TextbookSource) -> dict:
    return {
        "id": citation.id, "source_key": source.key, "title": source.title,
        "subject": source.subject, "publisher": source.publisher, "edition": source.edition,
        "chapter": citation.chapter or "", "section": citation.section or "",
        "page_start": citation.page_start, "page_end": citation.page_end,
        "note": citation.note or "", "status": citation.status,
        "verified_by": citation.verified_by,
        "verified_at": citation.verified_at.isoformat() if citation.verified_at else None,
    }


async def citations_for_targets(
    session: AsyncSession, target_type: str, target_ids: list[int] | tuple[int, ...],
) -> dict[int, list[dict]]:
    if target_type not in TARGET_MODELS or not target_ids:
        return {}
    rows = (await session.execute(
        select(ContentCitation, TextbookSource)
        .join(TextbookSource, TextbookSource.key == ContentCitation.source_key)
        .where(ContentCitation.target_type == target_type, ContentCitation.target_id.in_(set(target_ids)))
        .order_by(ContentCitation.target_id, TextbookSource.subject, ContentCitation.id)
    )).all()
    out: dict[int, list[dict]] = defaultdict(list)
    for citation, source in rows:
        out[citation.target_id].append(_out(citation, source))
    return dict(out)


async def citations_for_target(session: AsyncSession, target_type: str, target_id: int) -> list[dict]:
    return (await citations_for_targets(session, target_type, [target_id])).get(target_id, [])


def _normalized_input(item) -> tuple:
    page_start = item.page_start
    page_end = item.page_end if item.page_end is not None else page_start
    return (
        item.source_key.strip(), item.chapter.strip(), item.section.strip(), page_start, page_end,
        item.note.strip(), item.status,
    )


async def replace_citations(
    session: AsyncSession, target_type: str, target_id: int, items: list, admin_id: int,
) -> int:
    model = TARGET_MODELS.get(target_type)
    if model is None:
        raise HTTPException(422, "出处目标类型无效")
    if await session.get(model, target_id) is None:
        raise HTTPException(404, "内容不存在")
    normalized = [_normalized_input(item) for item in items]
    locations = [row[:5] for row in normalized]
    if len(locations) != len(set(locations)):
        raise HTTPException(400, "同一教材位置不能重复添加")
    source_keys = {row[0] for row in normalized}
    existing_sources = set((await session.execute(
        select(TextbookSource.key).where(TextbookSource.key.in_(source_keys), TextbookSource.active.is_(True))
    )).scalars()) if source_keys else set()
    missing = source_keys - existing_sources
    if missing:
        raise HTTPException(400, f"未知或停用的教材：{', '.join(sorted(missing))}")

    current_rows = (await session.execute(
        select(ContentCitation).where(
            ContentCitation.target_type == target_type, ContentCitation.target_id == target_id,
        ).order_by(ContentCitation.id)
    )).scalars().all()
    current = [
        (c.source_key, c.chapter or "", c.section or "", c.page_start,
         c.page_end if c.page_end is not None else c.page_start, c.note or "", c.status)
        for c in current_rows
    ]
    if current == normalized:
        return 0

    await session.execute(delete(ContentCitation).where(
        ContentCitation.target_type == target_type, ContentCitation.target_id == target_id,
    ))
    now = datetime.now(timezone.utc)
    for source_key, chapter, section, page_start, page_end, note, status in normalized:
        reviewed = status in ("verified", "disputed")
        session.add(ContentCitation(
            target_type=target_type, target_id=target_id, source_key=source_key,
            chapter=chapter, section=section, page_start=page_start, page_end=page_end,
            note=note, status=status,
            verification_origin='attributed' if reviewed else 'unreviewed',
            verified_by=admin_id if reviewed else None,
            verified_at=now if reviewed else None,
        ))
    await session.flush()
    return 1


def citation_label(citation: dict) -> str:
    location = " · ".join(x for x in (citation["chapter"], citation["section"]) if x)
    if citation["page_start"] is not None:
        end = citation["page_end"] or citation["page_start"]
        pages = f"第 {citation['page_start']} 页" if end == citation["page_start"] else f"第 {citation['page_start']}-{end} 页"
        location = " · ".join(x for x in (location, pages) if x)
    status = {"verified": "已核验", "disputed": "有争议", "unverified": "待核验"}[citation["status"]]
    base = f"{citation['publisher']}《{citation['title']}》{citation['edition']}"
    return f"{base}{(' · ' + location) if location else ''}（{status}）"
