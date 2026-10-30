"""First-pass work is assigned once; chapter links never create extra work."""

from collections import defaultdict
from datetime import timedelta
from math import ceil

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardProgress, PlanSnapshot, PlanTask, PlanTaskSection, UserPlan, UserPlanItem
from app.services import card_merges, practice_dedup, question_links
from app.services.question_groups import ordered_groups


async def clear(session: AsyncSession, uid: int) -> None:
    tasks = select(PlanTask.id).where(PlanTask.user_id == uid)
    await session.execute(delete(PlanTaskSection).where(PlanTaskSection.task_id.in_(tasks)))
    await session.execute(delete(PlanTask).where(PlanTask.user_id == uid))
    await session.execute(delete(PlanSnapshot).where(PlanSnapshot.user_id == uid))


async def _sync(session: AsyncSession, uid: int, tasks: list[PlanTask], mapping=None) -> None:
    from app.services.study import utcnow

    if mapping is None:
        mapping = await practice_dedup.mapping_for(session, uid, [t.target_id for t in tasks if t.kind == "question"])
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


def _smooth_round_robin(
    units: list[list[PlanTask]], buckets: list[tuple[str, str] | None],
) -> list[list[PlanTask]]:
    """Interleave chapter buckets in proportion to their pending task counts."""
    grouped = defaultdict(list)
    for unit, bucket in zip(units, buckets):
        grouped[bucket].append(unit)
    weights = {bucket: sum(len(unit) for unit in queue) for bucket, queue in grouped.items()}
    current = {bucket: 0 for bucket in grouped}
    order = {bucket: index for index, bucket in enumerate(grouped)}
    result = []
    while grouped:
        total_weight = sum(weights.values())
        for bucket in grouped:
            current[bucket] += weights[bucket]
        selected = max(grouped, key=lambda bucket: (current[bucket], -order[bucket]))
        current[selected] -= total_weight
        result.append(grouped[selected].pop(0))
        if not grouped[selected]:
            del grouped[selected]
            del weights[selected]
            del current[selected]
            del order[selected]
    return result


def _assign(
    plan: UserPlan,
    units: list[list[PlanTask]],
    start=None,
    unit_buckets: list[tuple[str, str] | None] | None = None,
) -> None:
    """Give cards and questions daily quotas; interleave chapters and keep cases whole."""
    if unit_buckets is None:
        unit_buckets = [None] * len(units)
    if len(unit_buckets) != len(units):
        raise ValueError("unit_buckets must align with units")
    pending = [([task for task in unit if task.completed_at is None], bucket)
               for unit, bucket in zip(units, unit_buckets)]
    for kind in ("card", "question"):
        track = [(unit, bucket) for unit, bucket in pending if unit and unit[0].kind == kind]
        ordered = _smooth_round_robin([unit for unit, _ in track], [bucket for _, bucket in track])
        total = sum(map(len, ordered))
        budget = max(1, ceil(total / plan.total_days))
        cursor = 0
        for unit in ordered:
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
    seeds = list(dict.fromkeys(qid for _, qids in content.values() for qid in qids))
    groups = await ordered_groups(session, seeds)
    mapping = await practice_dedup.mapping_for(session, uid, [qid for group in groups for qid in group])
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
    unit_buckets = []
    section_order = {(section.subject, section.part): index for index, section in enumerate(sections)}
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
                candidates = {pair for task in unit for pair in memberships[(task.kind, task.target_id)]}
                unit_buckets.append(min(candidates, key=lambda pair: section_order[pair]) if candidates else None)
    await session.flush()
    for key, task in tasks.items():
        for subject, part in memberships[key]:
            session.add(PlanTaskSection(task_id=task.id, subject=subject, part=part))
    await _sync(session, uid, list(tasks.values()), mapping)
    _assign(plan, units, unit_buckets=unit_buckets)
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
    mapping = await practice_dedup.mapping_for(session, uid, [t.target_id for t in tasks if t.kind == "question"])
    await _sync(session, uid, tasks, mapping)
    links = list((await session.scalars(select(PlanTaskSection).join(
        PlanTask, PlanTask.id == PlanTaskSection.task_id,
    ).where(PlanTask.user_id == uid))).all())
    tasks, links = await _canonicalize_questions(session, tasks, links, mapping)
    await session.flush()
    return tasks, links


async def _canonicalize_questions(session, tasks, links, mapping=None):
    """Reconcile derived assignments; original questions and attempts are kept."""
    if mapping is None:
        mapping = await question_links.redirects(session)
    groups = defaultdict(list)
    for task in tasks:
        if task.kind == "question":
            groups[question_links.resolve(mapping, task.target_id)].append(task)
    removed = set()
    retained_links = list(links)
    links_by_task = defaultdict(list)
    for link in links:
        links_by_task[link.task_id].append(link)
    for root, members in groups.items():
        # Keep an existing root row to avoid the unique target constraint. Its
        # assignment takes the earliest position and due date of all aliases.
        keep = min(members, key=lambda t: (t.target_id != root, t.position, t.id))
        keep.position = min(t.position for t in members)
        keep.due_day = min(t.due_day for t in members)
        completed = [t.completed_at for t in members if t.completed_at is not None]
        keep.completed_at = min(completed, key=lambda at: at.timestamp()) if completed else None
        member_ids = {t.id for t in members}
        existing_pairs = {(link.subject, link.part) for link in links_by_task[keep.id]}
        all_pairs = {(link.subject, link.part) for task_id in member_ids for link in links_by_task[task_id]}
        for subject, part in sorted(all_pairs - existing_pairs):
            link = PlanTaskSection(task_id=keep.id, subject=subject, part=part)
            session.add(link)
            retained_links.append(link)
        duplicate_ids = member_ids - {keep.id}
        if duplicate_ids:
            removed.update(duplicate_ids)
        keep.target_id = root
    if removed:
        # One bulk reconciliation, rather than autoflushing and scanning a large
        # identity map for every duplicate group. The retained root row wins
        # above, so no target rename can conflict with a row being removed.
        from app.services.question_groups import batches

        await session.flush()
        for chunk in batches(sorted(removed)):
            await session.execute(delete(PlanTaskSection).where(
                PlanTaskSection.task_id.in_(chunk),
            ).execution_options(synchronize_session="fetch"))
            await session.execute(delete(PlanTask).where(
                PlanTask.id.in_(chunk),
            ).execution_options(synchronize_session="fetch"))
    return (sorted((t for t in tasks if t.id not in removed), key=lambda t: (t.position, t.id)),
            [link for link in retained_links if link.task_id not in removed])


def relative_day(task: PlanTask, today) -> int:
    return max(1, (task.due_day - today).days + 1)


async def question_mapping(session, uid, extra_ids=()):
    ids = list((await session.scalars(select(PlanTask.target_id).where(
        PlanTask.user_id == uid, PlanTask.kind == "question",
    ))).all())
    return await practice_dedup.mapping_for(session, uid, [*ids, *extra_ids])


async def preview(session, uid, items, total_days):
    """Calculate a proposed workload without creating or restarting a plan."""
    from app.services import study

    sections = [UserPlanItem(user_id=uid, subject=s, part=p, ord=i) for i, (s, p) in enumerate(items)]
    content = await study._item_content(session, sections)
    cids = {cid for cards, _ in content.values() for cid in cards}
    seeds = list(dict.fromkeys(qid for _, questions in content.values() for qid in questions))
    groups = await ordered_groups(session, seeds)
    expanded = {qid for group in groups for qid in group}
    mapping = await practice_dedup.mapping_for(session, uid, list(expanded))
    roots = {question_links.resolve(mapping, qid) for qid in expanded}
    answered = await question_links.answered(session, uid, mapping)
    cmapping = await card_merges.redirects(session)
    seen_cards = {card_merges.resolve(cmapping, cid) for cid in (await session.scalars(
        select(CardProgress.card_id).where(CardProgress.user_id == uid, CardProgress.last_seen_at.isnot(None))
    )).all()}
    pending_q, pending_c = len(roots - answered.keys()), len(cids - seen_cards)
    return dict(cards=len(cids), questions=len(roots), pending_cards=pending_c, pending_questions=pending_q,
                daily_cards=ceil(pending_c / total_days), daily_questions=ceil(pending_q / total_days),
                duplicate_questions_skipped=len(expanded) - len(roots))


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
    tasks, links = await read(session, plan.user_id)
    # Only unfinished work moves; no completed task is recreated.
    groups = await ordered_groups(session, [t.target_id for t in tasks if t.kind == "question"])
    by_id = {t.target_id: t for t in tasks if t.kind == "question"}
    units = [[t] for t in tasks if t.kind == "card"]
    units += [[by_id[qid] for qid in group if qid in by_id] for group in groups]
    sections = list((await session.scalars(select(UserPlanItem).where(
        UserPlanItem.user_id == plan.user_id,
    ).order_by(UserPlanItem.ord, UserPlanItem.id))).all())
    section_order = {(section.subject, section.part): index for index, section in enumerate(sections)}
    memberships = defaultdict(set)
    by_task_id = {task.id: task for task in tasks}
    for link in links:
        task = by_task_id.get(link.task_id)
        if task is not None:
            memberships[(task.kind, task.target_id)].add((link.subject, link.part))
    unit_buckets = []
    for unit in units:
        candidates = {pair for task in unit for pair in memberships[(task.kind, task.target_id)]}
        unit_buckets.append(min(candidates, key=lambda pair: section_order[pair]) if candidates else None)
    _assign(plan, units, unit_buckets=unit_buckets)
