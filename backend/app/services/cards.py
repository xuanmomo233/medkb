from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md, md
from app.models import Card, CardProgress
from app.services import plan_queue, provenance
from app.services.card_merges import canonical_id, canonical_ids, details, visible
from app.services.progress import derive_state

LIMIT = 500
PLAN_LIMIT = 2000


async def index(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(Card.subject, Card.part, func.count(Card.id).label("n"))
            .where(visible())
            .group_by(Card.subject, Card.part)
            .order_by(Card.subject, Card.part)
        )
    ).all()
    return [{"subject": r.subject, "part": r.part, "count": r.n} for r in rows]


async def list_cards(
    session: AsyncSession, user_id: int, *, subject: str | None, part: str | None,
    ids: list[int] | None, plan_day: int | None, starred: bool, due: bool,
) -> list[dict]:
    stmt = select(Card, CardProgress).outerjoin(
        CardProgress, and_(CardProgress.card_id == Card.id, CardProgress.user_id == user_id)
    ).where(visible())
    limit = LIMIT
    if subject:
        stmt = stmt.where(Card.subject == subject)
    if part:
        stmt = stmt.where(Card.part == part)
    if ids:
        stmt = stmt.where(Card.id.in_(await canonical_ids(session, ids[:LIMIT])))
    if plan_day is not None:
        plan_ids = await plan_queue.targets(session, user_id, plan_day, "card")
        if not plan_ids:
            return []
        limit = max(PLAN_LIMIT, len(plan_ids))
        stmt = stmt.where(Card.id.in_(plan_ids))
    if starred:
        stmt = stmt.where(CardProgress.starred.is_(True))
    if due:
        stmt = stmt.where(CardProgress.in_plan.is_(True), CardProgress.due_at <= datetime.now(timezone.utc))
    stmt = stmt.order_by(Card.id).limit(limit)
    rows = (await session.execute(stmt)).all()
    info = await details(session, [c.id for c, _ in rows])
    citations = await provenance.citations_for_targets(session, "card", [c.id for c, _ in rows])
    out = []
    for c, p in rows:
        out.append({
            "id": c.id, "subject": c.subject, "part": c.part, "section": c.section or "",
            "term": c.term, "term_html": md(c.term), "hint": c.hint or "", "body_html": card_md(c.body),
            "state": derive_state(p), "starred": bool(p and p.starred),
            "citations": citations.get(c.id, []),
            **info.get(c.id, {}),
        })
    return out


async def get_admin_card(session: AsyncSession, card_id: int):
    from app.schemas.admin import AdminCard

    c = await session.get(Card, card_id)
    if c is None:
        raise HTTPException(404, "卡片不存在")
    return AdminCard(
        id=c.id, subject=c.subject or "", part=c.part or "", section=c.section or "",
        term=c.term or "", hint=c.hint or "", body=c.body or "",
        citations=await provenance.citations_for_target(session, "card", c.id),
    )


async def update_admin_card(session: AsyncSession, admin_id: int, card_id: int, patch) -> int:
    root = await canonical_id(session, card_id)
    if root != card_id:
        raise HTTPException(409, f"该原卡已合并到 #{root}，请编辑主卡")
    c = await session.get(Card, card_id)
    if c is None:
        raise HTTPException(404, "卡片不存在")
    changed = 0
    if patch.section is not None:
        new = patch.section.strip()
        if len(new) > 128:
            raise HTTPException(400, "分节不能超过 128 字")
        if new != (c.section or ""):
            c.section = new
            changed += 1
    if patch.term is not None:
        new = patch.term.strip()
        if not new:
            raise HTTPException(400, "卡片标题不能为空")
        if len(new) > 200:
            raise HTTPException(400, "卡片标题不能超过 200 字")
        if new != (c.term or ""):
            c.term = new
            changed += 1
    if patch.hint is not None:
        if len(patch.hint) > 2000:
            raise HTTPException(400, "提示不能超过 2000 字")
        if patch.hint != (c.hint or ""):
            c.hint = patch.hint
            changed += 1
    if patch.body is not None:
        if len(patch.body) > 20000:
            raise HTTPException(400, "正文过长（最多 20000 字）")
        if patch.body != (c.body or ""):
            c.body = patch.body
            changed += 1
    if patch.citations is not None:
        changed += await provenance.replace_citations(session, "card", card_id, patch.citations, admin_id)
    await session.commit()
    return changed

