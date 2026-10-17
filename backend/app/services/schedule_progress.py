"""A successful study write completes today's matching tasks, from any entry."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuestionProgress, ScheduleItem
from app.services import card_merges, question_links, sm2


async def complete(session: AsyncSession, uid: int, kind: str, targets: list[int]) -> set[int]:
    from app.services.study import local_today, utcnow

    if not targets:
        return set()
    mapping = await (question_links.redirects(session) if kind == "question" else card_merges.redirects(session))
    resolver = question_links.resolve if kind == "question" else card_merges.resolve
    roots = {resolver(mapping, target) for target in targets}
    items = (await session.scalars(select(ScheduleItem).where(
        ScheduleItem.user_id == uid, ScheduleItem.day == local_today(),
        ScheduleItem.item_type == kind, ScheduleItem.done_at.is_(None),
    ).with_for_update())).all()
    completed = set()
    now = utcnow()
    for item in items:
        root = resolver(mapping, item.item_id)
        if root in roots:
            item.done_at = now
            completed.add(root)
    return completed


async def questions(session: AsyncSession, uid: int, results: list[tuple[int, bool]]) -> None:
    from app.services.study import utcnow

    completed = await complete(session, uid, "question", [qid for qid, _ in results])
    mapping = await question_links.redirects(session)
    for qid, correct in results:
        root = question_links.resolve(mapping, qid)
        if root not in completed:
            continue
        completed.remove(root)  # Retries or repeated entries must not advance SRS twice.
        qp = await session.get(QuestionProgress, (uid, qid))
        if qp is not None:
            qp.reps, qp.ease, qp.interval_days, qp.due_at = sm2.rate(
                "rate_good" if correct else "rate_again", qp.reps, qp.ease, qp.interval_days, utcnow(),
            )
            qp.in_plan = True
