import random as _random
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, Question
from app.schemas import quiz as S
from app.services.quiz import Recorder, iso

SUBMIT_MAX = 500
MOCK_QTYPES = ("单选", "多选", "病例子题", "病例串")
_JUDGEABLE = re.compile(r"^[A-J]([^A-J]+[A-J])*$")
UNKNOWN_SYSTEM = "未细分"


async def submit(session: AsyncSession, uid: int, title: str, items: list[S.SubmitItem]) -> S.ExamReport:
    if not items:
        raise HTTPException(400, "交卷题目不能为空")
    if len(items) > SUBMIT_MAX:
        raise HTTPException(400, f"单次最多交卷 {SUBMIT_MAX} 题")
    qids = list({it.question_id for it in items})
    qs = {q.id: q for q in (await session.execute(select(Question).where(Question.id.in_(qids)))).scalars().all()}
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
    """1 单选 / 2 病例 / 3 多选"""
    if qtype in ("病例子题", "病例串"):
        return 2
    if qtype == "多选" or len(re.findall(r"[A-J]", answer or "")) > 1:
        return 3
    return 1


def build_mock(
    pool: list[tuple[int, str, bool, int]],
    n: int,
    freq: dict[str, int] | None = None,
    rng: _random.Random | None = None,
) -> list[int]:
    """pool: (id, system, is_real_exam, trank) 的列表；freq: system→真题题量权重。返回按 单选→病例→多选 排序的 ids。"""
    rng = rng or _random.Random()
    freq = dict(freq or {})
    freq[UNKNOWN_SYSTEM] = 1
    pools: dict[int, dict[str, list[tuple[int, bool]]]] = {1: {}, 2: {}, 3: {}}
    for qid, system, hot, tr in pool:
        pools[tr].setdefault(system or UNKNOWN_SYSTEM, []).append((qid, bool(hot)))
    quota = {1: round(n * 0.67), 2: max(1, round(n * 0.11))}
    quota[3] = n - quota[1] - quota[2]
    ids: list[int] = []
    for tr in (1, 2, 3):
        pl = pools[tr]
        if not pl:
            continue
        systems = list(pl)
        w = [freq.get(s, 1) for s in systems]
        tot = sum(w) or 1
        alloc = [min(len(pl[s]), round(quota[tr] * wi / tot)) for s, wi in zip(systems, w)]
        while sum(alloc) > quota[tr]:
            i = max(range(len(alloc)), key=lambda j: alloc[j])
            alloc[i] -= 1
        while sum(alloc) < quota[tr]:
            progressed = False
            for i in sorted(range(len(systems)), key=lambda j: -w[j]):
                if sum(alloc) >= quota[tr]:
                    break
                if alloc[i] < len(pl[systems[i]]):
                    alloc[i] += 1
                    progressed = True
            if not progressed:
                break
        for s, ki in zip(systems, alloc):
            qs = list(pl[s])
            rng.shuffle(qs)
            hot = [i for i, h in qs if h]
            cold = [i for i, h in qs if not h]
            n_hot = min(len(hot), round(ki * 0.7))
            ids += hot[:n_hot] + cold[: ki - n_hot]
            if len(hot) > n_hot and len(cold) < ki - n_hot:
                ids += hot[n_hot : n_hot + (ki - n_hot - len(cold))]
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
        if _JUDGEABLE.match(ans or "")
    ]
    return build_mock(pool, n, freq)
