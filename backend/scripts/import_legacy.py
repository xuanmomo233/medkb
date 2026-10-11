import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, insert, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.models import (  # noqa: E402
    Attempt, Card, CardProgress, CardQuestion, Chapter, Exam, Note, NoteLike, PlanDay,
    PlanDayPart, Question, QuestionEdit, QuestionProgress, ScheduleItem,
)
from app.services import legacy_import as li  # noqa: E402
from app.services.plan_seed import seed_plan  # noqa: E402

WIPE_ORDER = [NoteLike, Note, QuestionEdit, Attempt, Exam, ScheduleItem, QuestionProgress,
              CardProgress, CardQuestion, PlanDayPart, PlanDay, Question, Card, Chapter]
CHECK_MODELS = [Question, Card, Chapter, PlanDay]


def target_url_default() -> str:
    url = os.environ.get("MEDKB_DATABASE_URL")
    if url:
        return url
    from app.core.config import get_settings
    return get_settings().database_url


def log(msg: str) -> None:
    print(msg, flush=True)


async def reset_seq(session: AsyncSession) -> None:
    if session.bind.dialect.name != "postgresql":
        return
    for t in ("questions", "cards", "chapters"):
        await session.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{t}','id'), "
            f"COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)"))


async def insert_batches(session, model, rows, dry):
    if rows and not dry:
        await session.execute(insert(model), rows)


async def do_import(args) -> dict:
    legacy = li.open_legacy(args.legacy_url)
    tables = li.legacy_table_names(legacy)
    lc = li.legacy_counts(legacy)
    log(f"旧库行数: {lc}（卡片表={tables['cards']}）")
    stats = li.new_stats()
    dry = args.dry_run
    engine = None if dry else create_async_engine(args.target_url)

    async def work(session: AsyncSession | None):
        if session is not None:
            try:
                counts = {m.__tablename__: (await session.execute(
                    select(func.count()).select_from(m))).scalar_one() for m in CHECK_MODELS}
            except Exception as e:
                raise SystemExit(f"目标库读取失败（是否已运行 init_db.py？）: {e}")
            if any(counts.values()):
                if not args.wipe:
                    raise SystemExit(f"目标库非空 {counts}，拒绝导入；如需清空重建请加 --wipe")
                if not args.yes:
                    if not sys.stdin.isatty():
                        raise SystemExit("--wipe 需要 --yes 或交互确认")
                    if input(f"将清空内容表及依赖数据 {counts}，输入 yes 确认: ").strip() != "yes":
                        raise SystemExit("已取消")
                for m in WIPE_ORDER:
                    await session.execute(delete(m))
                log("已清空内容表")
            elif args.wipe and not args.yes and sys.stdin.isatty():
                if input("--wipe 目标库内容表为空，输入 yes 继续: ").strip() != "yes":
                    raise SystemExit("已取消")

        qmap: dict[str, int] = {}
        seen: set[str] = set()
        done = 0
        for rows in li.iter_legacy(legacy, tables["questions"], li.QUESTION_COLS, args.batch):
            mapped = li.prepare_questions(rows, seen, stats)
            for m in mapped:
                qmap.setdefault(li.norm_qid(m["qid"]), m["id"])
            if session is not None:
                await insert_batches(session, Question, mapped, dry)
            done += len(rows)
            log(f"questions {done}/{lc['questions']}")

        cdone = 0
        for rows in li.iter_legacy(legacy, tables["cards"], li.CARD_COLS, args.batch):
            cards, links = [], []
            for r in rows:
                cards.append(li._clip("cards", li.map_card(r), stats))
                links += li.build_card_links(int(r["id"]), r.get("qids"), qmap, stats)
            stats["cards"] += len(cards)
            stats["card_questions"] += len(links)
            if session is not None:
                await insert_batches(session, Card, cards, dry)
                await insert_batches(session, CardQuestion, links, dry)
            cdone += len(rows)
            log(f"cards {cdone}/{lc['cards']}")

        hdone = 0
        for rows in li.iter_legacy(legacy, tables["chapters"], li.CHAPTER_COLS, args.batch):
            chs = [li._clip("chapters", li.map_chapter(r), stats) for r in rows]
            stats["chapters"] += len(chs)
            stats["chapters_mindmap"] += sum(c["kind"] == "mindmap" for c in chs)
            stats["chapters_with_pages"] += sum(bool(c["pages"]) for c in chs)
            if session is not None:
                await insert_batches(session, Chapter, chs, dry)
            hdone += len(rows)
            log(f"chapters {hdone}/{lc['chapters']}")

        if session is not None:
            await session.flush()
            await reset_seq(session)
            n = await seed_plan(session)
            log(f"课表种子: {n} 天")

    try:
        if dry:
            await work(None)
        else:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                async with session.begin():
                    await work(session)
            log("事务已提交")
    finally:
        if engine is not None:
            await engine.dispose()
        legacy.dispose()
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="旧库 -> 新库内容数据迁移（用户数据不迁移）")
    p.add_argument("--legacy-url", required=True)
    p.add_argument("--target-url", default=None)
    p.add_argument("--batch", type=int, default=2000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--wipe", action="store_true")
    p.add_argument("--yes", action="store_true", help="跳过 --wipe 的交互确认")
    args = p.parse_args()
    if not args.dry_run and not args.target_url:
        args.target_url = target_url_default()
    t0 = time.time()
    stats = asyncio.run(do_import(args))
    log("映射统计:\n" + json.dumps(stats, ensure_ascii=False, indent=2))
    log(f"{'DRY-RUN ' if args.dry_run else ''}完成，用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
