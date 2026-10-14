from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, CardProgress, Question, QuestionProgress
from app.services import sm2
from app.services.card_merges import canonical_id

_MODELS = {
    "question": (Question, QuestionProgress, "question_id"),
    "card": (Card, CardProgress, "card_id"),
}


def derive_state(p) -> str:
    if p is None:
        return ""
    if p.mastered:
        return "mastered"
    if p.in_wrongbook:
        return "again"
    if p.in_plan:
        return "plan"
    return ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _apply(p, action: str, target_type: str, now: datetime) -> None:
    if action == "star":
        p.starred = True
        return
    if action == "unstar":
        p.starred = False
        return
    p.last_seen_at = now
    if action == "plan":
        if not p.in_plan or p.due_at is None:
            p.due_at = sm2.first_due(now)
        p.in_plan = True
    elif action == "unplan":
        p.in_plan = False
        p.due_at = None
    elif action == "wrong":
        p.in_wrongbook = True
    elif action == "unwrong":
        p.in_wrongbook = False
    elif action == "master":
        p.mastered = True
    elif action == "unmaster":
        p.mastered = False
    elif action.startswith("rate_"):
        p.reps, p.ease, p.interval_days, p.due_at = sm2.rate(
            action, p.reps, p.ease, p.interval_days, now
        )
        p.in_plan = True
        if action == "rate_again" and target_type == "card":
            p.in_wrongbook = True


async def mark(session: AsyncSession, user_id: int, target_type: str, target_id: int, action: str) -> bool:
    """返回 False 表示目标不存在。"""
    target_model, prog_model, fk = _MODELS[target_type]
    if target_type == "card":
        target_id = await canonical_id(session, target_id)
    if await session.get(target_model, target_id) is None:
        return False
    for attempt in range(2):
        p = (
            await session.execute(
                select(prog_model).where(prog_model.user_id == user_id, getattr(prog_model, fk) == target_id)
            )
        ).scalar_one_or_none()
        if p is None:
            p = prog_model(
                user_id=user_id, in_wrongbook=False, mastered=False, in_plan=False,
                starred=False, reps=0, ease=2.5, interval_days=0.0, **{fk: target_id},
            )
            session.add(p)
        _apply(p, action, target_type, _now())
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            if attempt:
                raise
    return True
