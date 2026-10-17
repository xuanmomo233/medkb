"""First-pass work is assigned once; chapter links never create extra work."""

from collections import defaultdict
from datetime import timedelta
from math import ceil

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardProgress, PlanSnapshot, PlanTask, PlanTaskSection, UserPlan, UserPlanItem
from app.services import card_merges, question_links
from app.services.question_groups import ordered_groups


async def clear(session: AsyncSession, uid: int) -> None:
    tasks = select(PlanTask.id).where(PlanTask.user_id == uid)
    await session.execute(delete(PlanTaskSection).where(PlanTaskSection.task_id.in_(tasks)))
    await session.execute(delete(PlanTask).where(PlanTask.user_id == uid))
    await session.execute(delete(PlanSnapshot).where(PlanSnapshot.user_id == uid))


async def _sync(session: AsyncSession, uid: int, tasks: list[PlanTask]) -> None:
    from app.services.study import utcnow

    mapping = await question_links.redirects(session)
    done_q = await question_links.answered(session, uid, mapping)
    cards = await card_merges.redirects(session)
    done_c = {}
    for cid, at in (await session.execute(select(CardProgress.card_id, CardProgress.last_seen_at).where(
        CardProgress.user_id == uid, CardProgress.last_seen_at.isnot(None),
    ))).all():
        done_c[card_merges.resolve(cards, cid)] = at
    for task in tasks:
        done = done_q if task.kind == "question" else done_c
        target = (question_links.resolve(mapping, task.target_id) if task.kind == "question"
                  else card_merges.resolve(cards, task.target_id))
        if task.completed_at is None and target in done:
            task.completed_at = done[target] or utcnow()
        elif task.kind == "question" and target not in done:
            task.completed_at = None


def _assign(plan: UserPlan, units: list[list[PlanTask]], start=None) -> None:
    """Give cards and questions daily quotas; keep each case together."""
    pending = [[task for task in unit if task.completed_at is None] for unit in units]
    for kind in ("card", "question"):
        track = [unit for unit in pending if unit and unit[0].kind == kind]
        total = sum(map(len, track))
        budget = max(1, ceil(total / plan.total_days))
        cursor = 0
        for unit in track:
            day = min(cursor // budget, plan.total_days - 1)
            for task in unit:
                task.due_day = (start or plan.start_day) + timedelta(days=day)
            cursor += len(unit)


async def _build(session: AsyncSession, plan: UserPlan) -> None:
    from app.services import study

    uid = plan.user_id
    sections = list((await session.scalars(select(UserPlanItem).where(
        UserPlanItem.user_id == uid,
    ).order_by(UserPlanItem.ord, UserPlanItem.id))).all())
    content = await study._item_content(session, sections)
    mapping = await question_links.redirects(session)
    seeds = list(dict.fromkeys(qid for _, qids in content.values() for qid in qids))
    groups = await ordered_groups(session, seeds)
    group_by_seed = {qid: group for group in groups for qid in group}
    # A task may satisfy several sections, but there is only one assignment.
    memberships = defaultdict(set)
    for section in sections:
        pair = (section.subject, section.part)
        cids, qids = content.get(study._item_key(*pair), ([], []))
        for cid in cids:
            memberships[("card", cid)].add(pair)
        for qid in qids:
            for child in group_by_seed.get(qid, (qid,)):
                memberships[("question", question_links.resolve(mapping, child))].add(pair)
    tasks = {}
    units = []
    for section in sections:
        cids, qids = content.get(study._item_key(section.subject, section.part), ([], []))
        work = [[("card", cid)] for cid in cids]
        work += [[("question", question_links.resolve(mapping, child))
                  for child in group_by_seed.get(qid, (qid,))] for qid in qids]
        for keys in work:
            unit = []
            for key in keys:
                if key in tasks:
                    continue
                task = PlanTask(user_id=uid, kind=key[0], target_id=key[1],
                                position=len(tasks), due_day=plan.start_day)
                session.add(task)
                tasks[key] = task
                unit.append(task)
            if unit:
                units.append(unit)
    await session.flush()
    for key, task in tasks.items():
        for subject, part in memberships[key]:
            session.add(PlanTaskSection(task_id=task.id, subject=subject, part=part))
    await _sync(session, uid, list(tasks.values()))
    _assign(plan, units)
    session.add(PlanSnapshot(user_id=uid))
    await session.flush()


async def read(session: AsyncSession, uid: int) -> tuple[list[PlanTask], list[PlanTaskSection]]:
    # Serialize initialization, configuration changes, and reads on PostgreSQL.
    plan = await session.scalar(select(UserPlan).where(UserPlan.user_id == uid).with_for_update())
    if plan is None:
        return [], []
    if await session.get(PlanSnapshot, uid) is None:
        await _build(session, plan)
    tasks = list((await session.scalars(select(PlanTask).where(
        PlanTask.user_id == uid,
    ).order_by(PlanTask.position))).all())
    await _sync(session, uid, tasks)
    links = list((await session.scalars(select(PlanTaskSection).join(
        PlanTask, PlanTask.id == PlanTaskSection.task_id,
    ).where(PlanTask.user_id == uid))).all())
    await session.flush()
    return tasks, links


def relative_day(task: PlanTask, today) -> int:
    return max(1, (task.due_day - today).days + 1)


async def targets(session: AsyncSession, uid: int, day: int, kind: str) -> list[int]:
    from app.services.study import local_today

    tasks, _ = await read(session, uid)
    today = local_today()
    out = [task.target_id for task in tasks if task.kind == kind and task.completed_at is None
           and relative_day(task, today) == day]
    await session.commit()
    return out


async def complete_questions(session: AsyncSession, uid: int, qids: list[int]) -> None:
    from app.services.study import utcnow
    from app.services.question_groups import batches

    mapping = await question_links.redirects(session)
    roots = list({question_links.resolve(mapping, qid) for qid in qids})
    for chunk in batches(roots):
        await session.execute(update(PlanTask).where(
            PlanTask.user_id == uid, PlanTask.kind == "question", PlanTask.target_id.in_(chunk),
            PlanTask.completed_at.is_(None),
        ).values(completed_at=utcnow()))


async def restart(session: AsyncSession, plan: UserPlan) -> None:
    tasks, _ = await read(session, plan.user_id)
    # Only unfinished work moves; no completed task is recreated.
    groups = await ordered_groups(session, [t.target_id for t in tasks if t.kind == "question"])
    by_id = {t.target_id: t for t in tasks if t.kind == "question"}
    units = [[t] for t in tasks if t.kind == "card"]
    units += [[by_id[qid] for qid in group if qid in by_id] for group in groups]
    _assign(plan, units)
