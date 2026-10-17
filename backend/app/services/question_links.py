"""Only explicit relationships are used. Reading never classifies or merges data."""

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, PlanTask, Question, QuestionMerge, QuestionProgress, QuestionRelation
from app.services.question_groups import batches


async def redirects(session: AsyncSession) -> dict[int, int]:
    return dict((await session.execute(select(QuestionMerge.alias_id, QuestionMerge.canonical_id))).all())


def resolve(mapping: dict[int, int], qid: int) -> int:
    seen = set()
    while qid in mapping:
        if qid in seen:
            raise HTTPException(409, "题目合并关系存在循环，请管理员修复")
        seen.add(qid)
        qid = mapping[qid]
    return qid


async def answered(session: AsyncSession, uid: int, mapping: dict[int, int]) -> dict[int, object]:
    rows = (await session.execute(
        select(Attempt.question_id, func.max(Attempt.created_at))
        .where(Attempt.user_id == uid, Attempt.picked != "")
        .group_by(Attempt.question_id)
    )).all()
    # Explicitly marking a question mastered also satisfies a first-pass task.
    rows += (await session.execute(
        select(QuestionProgress.question_id, QuestionProgress.last_seen_at)
        .where(QuestionProgress.user_id == uid, QuestionProgress.mastered.is_(True))
    )).all()
    out = {}
    for qid, at in rows:
        root = resolve(mapping, qid)
        if root not in out or (at is not None and (out[root] is None or at.timestamp() > out[root].timestamp())):
            out[root] = at
    return out


async def related(session: AsyncSession, uid: int, qid: int, limit: int = 3) -> list[dict]:
    if await session.get(Question, qid) is None:
        raise HTTPException(404, "题目不存在")
    mapping = await redirects(session)
    root = resolve(mapping, qid)
    aliases = [root, *(alias for alias in mapping if resolve(mapping, alias) == root)]
    relations = []
    for chunk in batches(aliases):
        relations += (await session.scalars(select(QuestionRelation).where(
            or_(QuestionRelation.left_id.in_(chunk), QuestionRelation.right_id.in_(chunk))
        ).order_by(QuestionRelation.id))).all()
    if not relations:
        return []
    seen = await answered(session, uid, mapping)
    candidates = {}
    for rel in relations:
        left, right = resolve(mapping, rel.left_id), resolve(mapping, rel.right_id)
        other = right if left == root else left
        if other != root and other not in seen:
            candidates.setdefault(other, rel)
    if not candidates:
        return []
    pending = set((await session.scalars(select(PlanTask.target_id).where(
        PlanTask.user_id == uid, PlanTask.kind == "question", PlanTask.completed_at.is_(None),
    ))).all())
    by_id = {}
    for chunk in batches(list(candidates)):
        by_id.update((q.id, q) for q in (await session.scalars(select(Question).where(Question.id.in_(chunk)))).all())
    labels = {"variant": "同考法变式", "same_concept": "同考点巩固", "contrast": "易混点辨析"}
    from app.services.quiz import snippet
    out = []
    for target, rel in candidates.items():
        q = by_id.get(target)
        if q is not None:
            out.append(dict(id=q.id, qid=q.qid, chapter=q.chapter, qtype=q.qtype,
                            stem=snippet(q.stem), kind=rel.kind, label=labels[rel.kind],
                            reason=rel.reason, in_plan=target in pending))
        if len(out) >= limit:
            break
    return out
