from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md
from app.models import Card, CardMerge, CardOriginal, CardRelation


def visible(column=Card.id):
    return ~select(CardMerge.alias_id).where(CardMerge.alias_id == column).exists()


async def redirects(session: AsyncSession) -> dict[int, int]:
    return dict((await session.execute(select(CardMerge.alias_id, CardMerge.canonical_id))).all())


def resolve(mapping: dict[int, int], card_id: int) -> int:
    seen = set()
    while card_id in mapping:
        if card_id in seen:
            raise HTTPException(409, "卡片合并记录存在循环，需管理员修复")
        seen.add(card_id)
        card_id = mapping[card_id]
    return card_id


async def canonical_ids(session: AsyncSession, ids: Sequence[int]) -> list[int]:
    mapping = await redirects(session)
    return list(dict.fromkeys(resolve(mapping, card_id) for card_id in ids))


async def canonical_id(session: AsyncSession, card_id: int) -> int:
    return (await canonical_ids(session, [card_id]))[0]


async def original_ids(session: AsyncSession, card_id: int) -> list[int]:
    mapping = await redirects(session)
    root = resolve(mapping, card_id)
    return [root, *(alias for alias in sorted(mapping) if resolve(mapping, alias) == root)]


async def details(session: AsyncSession, ids: Sequence[int]) -> dict[int, dict]:
    if not ids:
        return {}
    mapping = await redirects(session)
    out = {card_id: {"related_cards": [], "original_cards": []} for card_id in ids}
    relations = (await session.scalars(select(CardRelation).where(
        or_(CardRelation.left_id.in_(ids), CardRelation.right_id.in_(ids))
    ))).all()
    other_ids = {resolve(mapping, i) for row in relations for i in (row.left_id, row.right_id)}
    others = {card.id: card for card in (await session.scalars(
        select(Card).where(Card.id.in_(other_ids))
    )).all()} if other_ids else {}
    for row in relations:
        for source, target in ((row.left_id, row.right_id), (row.right_id, row.left_id)):
            source, target = resolve(mapping, source), resolve(mapping, target)
            if source in out and target != source and target in others:
                card = others[target]
                out[source]["related_cards"].append({
                    "id": target, "term": card.term, "subject": card.subject,
                    "part": card.part, "reason": row.reason,
                })
    source_ids = set(ids) | {i for i in mapping if resolve(mapping, i) in out}
    for saved in (await session.scalars(select(CardOriginal).where(
        CardOriginal.card_id.in_(source_ids)
    ).order_by(CardOriginal.card_id))).all():
        root = resolve(mapping, saved.card_id)
        if root in out:
            card = saved.data
            out[root]["original_cards"].append({
                "id": saved.card_id, "term": card["term"], "subject": card["subject"],
                "part": card["part"], "section": card["section"], "hint": card["hint"],
                "source_file": card["source_file"],
                "body_html": card_md(card["body"]),
            })
    return out
