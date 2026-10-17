import random as _random
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, Question
from app.schemas import quiz as S
from app.services.quiz import Recorder, iso
from app.services.question_groups import batches, ordered_groups
from app.services import plan_queue, schedule_progress

# Up to 5,000 explicit seeds may each expand to four case children.
SUBMIT_MAX = 20_000
MOCK_QTYPES = ("单选", "多选", "病例子题", "病例串")
_JUDGEABLE = re.compile(r"[A-J]+(?:[\s,，、/;；]+[A-J]+)*")
UNKNOWN_SYSTEM = "未细分"


async def submit(session: AsyncSession, uid: int, title: str, items: list[S.SubmitItem]) -> S.ExamReport:
    if not items:
        raise HTTPException(400, "交卷题目不能为空")
    if len(items) > SUBMIT_MAX:
        raise HTTPException(400, f"单次最多交卷 {SUBMIT_MAX} 题")
    qids = list({it.question_id for it in items})
    qs = {}
    for chunk in batches(qids):
        qs.update((q.id, q) for q in (await session.execute(
            select(Question).where(Question.id.in_(chunk))
        )).scalars().all())
    title = (title or "").strip()[:80]
    exam = None
    if title:
        exam = Exam(user_id=uid, title=title, total=0, correct=0)
        session.add(exam)
        await session.flush()
    rec = await Recorder.create(session, uid, list(qs))
    results: list[S.SubmitResult] = []
    wrong_ids: list[int] = []
    by_ch: dict[str, list[int]] = {}
    total = correct = 0
    for it in items:
        q = qs.get(it.question_id)
        if q is None:
            continue
        ok = rec.judge(q, it.picked, exam.id if exam else None)
        if ok is None:
            results.append(S.SubmitResult(question_id=q.id, judged=False, answer=q.answer or ""))
            continue
        total += 1
        correct += ok
        a = by_ch.setdefault(q.chapter or "未分类", [0, 0])
        a[0] += 1
        a[1] += ok
        results.append(S.SubmitResult(question_id=q.id, judged=True, correct=ok, answer=q.answer or ""))
        if not ok:
            wrong_ids.append(q.id)
    if exam:
        exam.total, exam.correct = total, correct
    await plan_queue.complete_questions(session, uid, [r.question_id for r in results if r.judged])
    await schedule_progress.questions(session, uid, [(r.question_id, r.correct) for r in results if r.judged])
    await session.commit()
    return S.ExamReport(
        total=total, correct=correct,
        score_100=round(100 * correct / total) if total else 0,
        score_300=round(300 * correct / total) if total else 0,
        wrong_ids=wrong_ids,
        by_chapter=[
            S.ChapterScore(chapter=k, total=v[0], correct=v[1], rate=round(100 * v[1] / v[0]))
            for k, v in sorted(by_ch.items(), key=lambda kv: -kv[1][0])
        ],
        results=results,
    )


async def exams(session: AsyncSession, uid: int) -> list[S.ExamRecord]:
    rows = (
        await session.execute(
            select(Exam).where(Exam.user_id == uid).order_by(Exam.created_at.desc(), Exam.id.desc()).limit(50)
        )
    ).scalars().all()
    return [
        S.ExamRecord(
            id=e.id, created_at=iso(e.created_at) or "", title=e.title or "", total=e.total, correct=e.correct,
            rate=round(100 * e.correct / e.total) if e.total else 0,
        )
        for e in rows
    ]


# ---------------- 模考抽题 ----------------
def type_rank(qtype: str, answer: str) -> int:
    """Classify every child by its actual answer, even inside a case."""
    return 3 if len(set(re.findall(r"[A-J]", (answer or "").upper()))) > 1 else 1


def _reachable_size(counts: dict[int, int], target: int) -> bool:
    reachable = 1
    mask = (1 << (target + 1)) - 1
    for size, available in counts.items():
        available = min(available, target // size)
        block = 1
        while available:
            take = min(block, available)
            reachable = (reachable | (reachable << (take * size))) & mask
            available -= take
            block *= 2
    return bool(reachable & (1 << target))


def build_mock(
    pool: list[tuple[int, str, bool, int]],
    n: int,
    freq: dict[str, int] | None = None,
    rng: _random.Random | None = None,
    groups: dict[int, tuple[int, ...]] | None = None,
) -> list[int]:
    """Sample atomic cases, budgeting each child by its own single/multi answer.

    pool contains (id, system, real_exam, answer_type). Groups must include
    metadata for every member, including children ineligible as mock seeds.
    Case adjacency takes precedence over an impossible exact child count.
    """
    if n <= 0:
        return []
    rng = rng or _random.Random()
    groups = groups or {}
    by_id = {i: (system or UNKNOWN_SYSTEM, bool(hot), tr) for i, system, hot, tr in pool}
    # Bucket by contributions (not a single representative question's type).
    # This keeps selection bounded by the number of systems/case shapes rather
    # than repeatedly scanning the entire ~69k-question mock pool.
    buckets: dict[tuple[str, int, int, int], list[tuple[int, ...]]] = {}
    used = set()
    available: dict[str, int] = {}
    for qid in by_id:
        if qid in used:
            continue
        children = tuple(sorted(groups.get(qid, (qid,))))
        if any(child not in by_id for child in children):
            raise ValueError("mock pool must include every case child")
        used.update(children)
        system = by_id[children[0]][0]
        singles = sum(by_id[i][2] != 3 for i in children)
        multis = len(children) - singles
        hot = sum(by_id[i][1] for i in children)
        buckets.setdefault((system, singles, multis, hot), []).append(children)
        available[system] = available.get(system, 0) + len(children)
    for units in buckets.values():
        rng.shuffle(units)
    freq = freq or {}
    weights = {s: max(0, freq.get(s, 1)) for s in available}
    total_weight = sum(weights.values()) or 1
    target_system = {s: min(available[s], round(n * w / total_weight)) for s, w in weights.items()}
    quota = {1: round(n * 0.78), 3: n - round(n * 0.78)}
    count_type = {1: 0, 3: 0}
    count_system = {s: 0 for s in available}
    hot_count = case_count = 0
    ids: list[int] = []
    size_counts: dict[int, int] = {}
    for key, units in buckets.items():
        size = key[1] + key[2]
        size_counts[size] = size_counts.get(size, 0) + len(units)
    while len(ids) < n:
        remaining = n - len(ids)
        choices = [(key, units) for key, units in buckets.items() if units]
        if not choices:
            break
        fitting = [(key, units) for key, units in choices if key[1] + key[2] <= remaining]
        if _reachable_size(size_counts, remaining):
            viable = set()
            for size, count in size_counts.items():
                if size > remaining or not count:
                    continue
                reduced = {**size_counts, size: count - 1}
                if _reachable_size(reduced, remaining - size):
                    viable.add(size)
            fitting = [(key, units) for key, units in fitting if key[1] + key[2] in viable]
        # Prefer a fitting case, if any. Otherwise complete a final case.
        choices = fitting or choices
        def priority(entry):
            system, singles, multis, hot = entry[0]
            size = singles + multis
            type_gain = min(singles, max(0, quota[1] - count_type[1])) + min(multis, max(0, quota[3] - count_type[3]))
            system_gain = min(size, max(0, target_system[system] - count_system[system]))
            hot_gain = min(hot, max(0, round(n * 0.7) - hot_count))
            case_gain = min(size, max(0, round(n * 0.11) - case_count)) if size > 1 else 0
            # Keep the historical ~11% case share while allocating each
            # child's single/multi type separately. Weight equal shapes by
            # their remaining pool size instead of over-sampling rare cases.
            return ((4 * type_gain + 2 * system_gain + hot_gain + 3 * case_gain) / size,
                    -max(0, size - remaining), rng.random() ** (1 / len(entry[1])))
        key, units = max(choices, key=priority)
        children = units.pop()
        size_counts[len(children)] -= 1
        ids.extend(children)
        system, singles, multis, hot = key
        count_type[1] += singles
        count_type[3] += multis
        count_system[system] += len(children)
        hot_count += hot
        if len(children) > 1:
            case_count += len(children)
    return ids


async def mock(session: AsyncSession, n: int) -> list[int]:
    n = min(max(n, 10), 400)
    freq = {
        (s or UNKNOWN_SYSTEM): int(c)
        for s, c in (
            await session.execute(
                select(Question.system, func.count(Question.id)).where(Question.is_real_exam.is_(True)).group_by(Question.system)
            )
        ).all()
    }
    rows = (
        await session.execute(
            select(Question.id, Question.system, Question.is_real_exam, Question.qtype, Question.answer)
            .where(Question.qtype.in_(MOCK_QTYPES))
        )
    ).all()
    pool = [
        (i, s or UNKNOWN_SYSTEM, bool(hot), type_rank(qt, ans))
        for i, s, hot, qt, ans in rows
        if _JUDGEABLE.fullmatch((ans or "").strip().upper())
    ]
    eligible = {item[0] for item in pool}
    # Only cases have a parent stem. Scan narrow IDs, not unbounded question
    # ORM objects/text; then complete eligible case seeds regardless of whether
    # a sibling itself passed the mock's answer/type seed rules.
    grouped = (await session.execute(
        select(Question.id).where(Question.qtype.in_(MOCK_QTYPES), Question.parent_stem != "")
    )).scalars().all()
    case_seeds = [qid for qid in grouped if qid in eligible]
    groups = await ordered_groups(session, case_seeds)
    by_id = {item[0]: item for item in pool}
    missing = [qid for children in groups for qid in children if qid not in by_id]
    for chunk in batches(missing):
        for i, s, hot, qt, ans in (await session.execute(
            select(Question.id, Question.system, Question.is_real_exam, Question.qtype, Question.answer)
            .where(Question.id.in_(chunk))
        )).all():
            by_id[i] = (i, s or UNKNOWN_SYSTEM, bool(hot), type_rank(qt, ans))
    group_map = {qid: children for children in groups for qid in children}
    return build_mock(list(by_id.values()), n, freq, groups=group_map)
