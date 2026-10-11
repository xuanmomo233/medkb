import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, func, or_, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.models import Card, CardQuestion, Chapter, PlanDay, PlanDayPart, Question  # noqa: E402


async def scalar(s, stmt):
    return (await s.execute(stmt)).scalar_one()


async def report(url: str, legacy_url: str | None) -> bool:
    engine = create_async_engine(url)
    ok = True
    async with AsyncSession(engine) as s:
        nq = await scalar(s, select(func.count()).select_from(Question))
        nc = await scalar(s, select(func.count()).select_from(Card))
        nh = await scalar(s, select(func.count()).select_from(Chapter))
        ncq = await scalar(s, select(func.count()).select_from(CardQuestion))
        npd = await scalar(s, select(func.count()).select_from(PlanDay))
        print("== 行数 ==")
        print(f"questions={nq} cards={nc} card_questions={ncq} chapters={nh} plan_days={npd}")

        print("== questions 按 subject_dir / is_real_exam ==")
        rows = (await s.execute(select(Question.subject_dir, Question.is_real_exam, func.count())
                                .group_by(Question.subject_dir, Question.is_real_exam)
                                .order_by(Question.subject_dir, Question.is_real_exam))).all()
        for sd, real, n in rows:
            print(f"  {sd or '(空)'} 真题={bool(real)}: {n}")

        unlinked = await scalar(s, select(func.count()).select_from(Card).where(
            ~Card.id.in_(select(CardQuestion.card_id))))
        print(f"== cards == 总数={nc} 关联条数={ncq} 未关联卡片={unlinked}")

        print("== chapters ==")
        chs = (await s.execute(select(Chapter.kind, Chapter.pages))).all()
        by: dict[str, list[int]] = {}
        for kind, pages in chs:
            c = by.setdefault(kind, [0, 0])
            c[0] += 1
            c[1] += bool(pages)
        for kind, (n, wp) in by.items():
            print(f"  {kind}: {n}（pages 非空 {wp}）")

        print("== plan_days ==")
        days = (await s.execute(select(PlanDay).order_by(PlanDay.day_no))).scalars().all()
        for d in days:
            parts = (await s.execute(select(PlanDayPart).where(PlanDayPart.day_no == d.day_no))).scalars().all()
            cond = or_(*[and_(Card.subject == p.subject, Card.part == p.part) for p in parts]) if parts else None
            n = await scalar(s, select(func.count()).select_from(Card).where(cond)) if cond is not None else 0
            zero = []
            for p in parts:
                if not await scalar(s, select(func.count()).select_from(Card).where(
                        Card.subject == p.subject, Card.part == p.part)):
                    zero.append(p.part)
            flag = "" if n else "  <-- 卡片数为 0"
            print(f"  第{d.day_no}天 {d.title}: parts={len(parts)} 卡片={n}{flag}")
            if zero:
                print(f"      无卡片的 part: {zero}")
            if not n:
                ok = False

        print("== 随机抽 5 题 ==")
        for q in (await s.execute(select(Question).order_by(func.random()).limit(5))).scalars():
            print(f"  id={q.id} qid={q.qid} options={len(q.options or [])} 项 answer={q.answer!r}")
        if nq:
            ne = await scalar(s, select(func.count()).select_from(Question).where(Question.answer == ""))
            no = len([1 for (o,) in (await s.execute(select(Question.options))).all() if o])
            print(f"  全量: answer 非空比例={(nq - ne) / nq:.1%}，options 非空比例={no / nq:.1%}")

    await engine.dispose()

    if legacy_url:
        from app.services import legacy_import as li
        eng = li.open_legacy(legacy_url)
        lc = li.legacy_counts(eng)
        eng.dispose()
        print("== 与旧库对比 ==")
        for k, new in (("questions", nq), ("cards", nc), ("chapters", nh)):
            same = lc[k] == new
            ok &= same
            print(f"  {k}: 旧={lc[k]} 新={new} {'守恒' if same else '不一致'}")
        print("（提示：questions 差异通常来自旧库重复/空 qid 被跳过，见导入统计 questions_dup_qid）")
        print("结论:", "守恒" if all(lc[k] == v for k, v in
                                  (("questions", nq), ("cards", nc), ("chapters", nh))) else "不一致")
    return ok


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--target-url", default=None)
    p.add_argument("--legacy-url", default=None)
    a = p.parse_args()
    url = a.target_url or os.environ.get("MEDKB_DATABASE_URL")
    if not url:
        from app.core.config import get_settings
        url = get_settings().database_url
    ok = asyncio.run(report(url, a.legacy_url))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
