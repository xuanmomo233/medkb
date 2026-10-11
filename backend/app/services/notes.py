from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Note, NoteLike, Question, User
from app.services.content import plain

_TARGETS = {"question": Question, "card": Card}


async def target_exists(session: AsyncSession, target_type: str, target_id: int) -> bool:
    return await session.get(_TARGETS[target_type], target_id) is not None


def _out(n: Note, preview: str | None = None) -> dict:
    return {
        "id": n.id, "target_type": n.target_type, "target_id": n.target_id, "body": n.body,
        "is_public": n.is_public, "created_at": n.created_at, "stem_preview": preview,
    }


async def list_for_target(session: AsyncSession, user_id: int, target_type: str | None, target_id: int | None) -> list[dict]:
    stmt = select(Note).where(Note.user_id == user_id)
    if target_type:
        stmt = stmt.where(Note.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(Note.target_id == target_id)
    stmt = stmt.order_by(Note.updated_at.desc(), Note.id.desc()).limit(500)
    return [_out(n) for n in (await session.execute(stmt)).scalars()]


async def list_mine(session: AsyncSession, user_id: int) -> list[dict]:
    notes = (
        await session.execute(
            select(Note).where(Note.user_id == user_id).order_by(Note.updated_at.desc(), Note.id.desc()).limit(500)
        )
    ).scalars().all()
    qids = {n.target_id for n in notes if n.target_type == "question"}
    stems: dict[int, str] = {}
    if qids:
        rows = (await session.execute(select(Question.id, Question.stem).where(Question.id.in_(qids)))).all()
        stems = {r.id: plain(r.stem)[:60] for r in rows}
    return [_out(n, stems.get(n.target_id, "") if n.target_type == "question" else None) for n in notes]


async def create(session: AsyncSession, user_id: int, target_type: str, target_id: int, body: str, is_public: bool) -> bool:
    if not await target_exists(session, target_type, target_id):
        return False
    session.add(Note(user_id=user_id, target_type=target_type, target_id=target_id, body=body, is_public=is_public))
    await session.commit()
    return True


async def delete_own(session: AsyncSession, user_id: int, note_id: int) -> bool:
    n = (await session.execute(select(Note).where(Note.id == note_id, Note.user_id == user_id))).scalar_one_or_none()
    if n is None:
        return False
    await session.execute(delete(NoteLike).where(NoteLike.note_id == note_id))
    await session.delete(n)
    await session.commit()
    return True


async def list_public(session: AsyncSession, user_id: int, target_type: str, target_id: int) -> list[dict]:
    likes = func.count(NoteLike.user_id).label("likes")
    rows = (
        await session.execute(
            select(Note, User.username, likes)
            .join(User, User.id == Note.user_id)
            .outerjoin(NoteLike, NoteLike.note_id == Note.id)
            .where(Note.target_type == target_type, Note.target_id == target_id, Note.is_public.is_(True))
            .group_by(Note.id, User.username)
            .order_by(likes.desc(), Note.id)
            .limit(500)
        )
    ).all()
    ids = [r[0].id for r in rows]
    liked: set[int] = set()
    if ids:
        liked = set(
            (await session.execute(select(NoteLike.note_id).where(NoteLike.user_id == user_id, NoteLike.note_id.in_(ids)))).scalars()
        )
    return [
        {
            "id": n.id, "body": n.body, "created_at": n.created_at, "username": uname,
            "likes": cnt, "liked": n.id in liked, "mine": n.user_id == user_id,
        }
        for n, uname, cnt in rows
    ]


async def toggle_like(session: AsyncSession, user_id: int, note_id: int) -> dict | None:
    n = await session.get(Note, note_id)
    if n is None or not n.is_public:
        return None
    existing = await session.get(NoteLike, (note_id, user_id))
    if existing:
        await session.delete(existing)
        liked = False
    else:
        session.add(NoteLike(note_id=note_id, user_id=user_id))
        liked = True
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        liked = True
    cnt = (await session.execute(select(func.count()).select_from(NoteLike).where(NoteLike.note_id == note_id))).scalar_one()
    return {"likes": cnt, "liked": liked}
