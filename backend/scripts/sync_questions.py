"""CLI: stage upstream data -> analyze -> report -> explicitly publish decisions."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import dispose_engine, get_engine  # noqa: E402
from app.models import Question, SyncCursor, SyncDocument, SyncRevision, SyncRun  # noqa: E402
from app.services.question_sync import analysis, store  # noqa: E402
from app.services.question_sync.publish import publish  # noqa: E402
from app.services.question_sync.schemas import ReviewPlan  # noqa: E402
from app.services.question_sync.upstream import AuthenticationRequired, WcykClient  # noqa: E402


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="按 ID 发现新题或回扫旧题，保存独立水位")
    scan.add_argument("--lane", choices=("frontier", "backfill"), default="frontier")
    scan.add_argument("--start", type=int, help="只在该水位首次建立时使用")
    scan.add_argument("--count", type=int, default=500)
    commands.add_parser("catalog", help="遍历题库与章节，发现低 ID 新题及旧题修订")
    probe = commands.add_parser("probe", help="只读核对登录、题目及章节分页接口")
    probe.add_argument("--qid", type=int, default=235290)
    load = commands.add_parser("import-json", help="离线上游原文导入，不发布")
    load.add_argument("file", type=Path)
    analyze = commands.add_parser("analyze", help="仅分析新增或变更版本")
    analyze.add_argument("--limit", type=int, default=50)
    analyze.add_argument("--rules-only", action="store_true", help="不用模型，仅给出差异、严格重复和已确认映射")
    analyze.add_argument("--refresh-pending", action="store_true", help="重新分析待审提案，旧复核哈希随之失效")
    report = commands.add_parser("report", help="标准输出完整 JSON 差异报告")
    report.add_argument("--limit", type=int, default=500)
    report.add_argument("--output", type=Path, help="写入新 JSON 报告文件，不覆盖已有文件")
    report.add_argument("--review-template", type=Path, help="生成待人工填写的复核清单")
    review = commands.add_parser("publish", help="按人工复核 JSON 清单发布")
    review.add_argument("file", type=Path)
    review.add_argument("--actor", type=int, required=True)
    review.add_argument("--dry-run", action="store_true")
    commands.add_parser("status", help="查看水位和最近运行记录")
    return root


async def run(args):
    try:
        async with AsyncSession(get_engine(), expire_on_commit=False) as session:
            if args.command in ("scan", "catalog", "probe"):
                client = WcykClient(get_settings().wcyk_token.get_secret_value())
                try:
                    if args.command == "probe":
                        records = await client.question(args.qid)
                        raw, meta = records[0]
                        bank = client._banks[meta["bank_id"]]
                        chapter = client._chapters[(meta["bank_id"], meta["chapter_id"])]
                        first, more = await client.chapter_page(bank, chapter, 1)
                        second = []
                        if more:
                            second, _ = await client.chapter_page(bank, chapter, 2)
                            if {str(r["id"]) for r, _ in first} & {str(r["id"]) for r, _ in second}:
                                raise ValueError("上游章节分页重复，不能确认目录完整性")
                        return dict(authenticated=True, qid=args.qid, records=len(records), bank_id=meta["bank_id"],
                                    chapter_id=meta["chapter_id"], first_page=len(first), second_page=len(second), has_more=more)
                    if args.command == "catalog":
                        return await store.catalog(session, client)
                    start = args.start
                    if start is None:
                        if args.lane == "backfill":
                            start = 1
                        else:
                            values = (await session.scalars(select(Question.qid))).all()
                            start = max((int(qid) for qid in values if qid.isdigit()), default=0) + 1
                    return await store.scan(session, client, scope=args.lane, start=start, count=args.count)
                finally:
                    await client.close()
            if args.command == "import-json":
                records = json.loads(args.file.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    raise ValueError("导入文件必须是 [{raw: 上游题目, source_meta: 来源信息}] 数组")
                counts = dict(new=0, changed=0, unchanged=0, invalid=0)
                for record in records:
                    counts[await store.ingest(session, record["raw"], record["source_meta"])] += 1
                await session.commit()
                return counts
            if args.command == "analyze":
                failures = []
                proposals = await analysis.analyze(session, limit=args.limit, use_ai=not args.rules_only,
                    refresh_pending=args.refresh_pending, errors=failures)
                return {"proposals": proposals, "failures": failures}
            if args.command == "report":
                if not 1 <= args.limit <= 500:
                    raise ValueError("报告数量应为 1–500")
                data = await analysis.report(session, limit=args.limit)
                outputs = []
                if args.output:
                    outputs.append((args.output, data))
                if args.review_template:
                    outputs.append((args.review_template, {"version": 1, "decisions": [dict(
                        proposal_id=item["proposal_id"], proposal_hash=item["proposal_hash"], action="review",
                        fields=item["suggestion"]["field_changes"], accept_classification=False,
                        acknowledge_conflicts=False, duplicate_of=None, relation_ids=[], card_ids=[], citation_ids=[],
                        note="请填写复核依据，并将 action 改为 publish 或 reject",
                    ) for item in data if not item["stale"]]}))
                for path, _ in outputs:
                    if path.exists():
                        raise ValueError(f"报告文件已存在：{path}")
                if len({path.resolve() for path, _ in outputs}) != len(outputs):
                    raise ValueError("差异报告和复核清单必须使用不同文件名")
                for path, content in outputs:
                    with path.open("x", encoding="utf-8", newline="\n") as stream:
                        json.dump(content, stream, ensure_ascii=False, indent=2)
                return {"count": len(data), "files": [str(p) for p, _ in outputs]} if outputs else data
            if args.command == "publish":
                result = await publish(session, ReviewPlan.model_validate_json(args.file.read_text(encoding="utf-8")), args.actor)
                if args.dry_run:
                    await session.rollback()
                else:
                    await session.commit()
                return {"dry_run": args.dry_run, "results": result}
            cursors = (await session.scalars(select(SyncCursor).order_by(SyncCursor.scope))).all()
            runs = (await session.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(30))).all()
            invalid = (await session.scalars(select(SyncDocument).where(SyncDocument.validation_error != "").order_by(SyncDocument.id).limit(100))).all()
            failed_analysis = (await session.scalars(select(SyncRevision).join(SyncDocument).where(
                SyncRevision.analysis_error != "", SyncDocument.latest_version == SyncRevision.version,
            ).order_by(SyncRevision.id).limit(100))).all()
            return dict(cursors=[dict(scope=c.scope, next_id=c.next_id, lease_until=str(c.lease_until)) for c in cursors],
                        invalid=[dict(external_id=d.external_id, error=d.validation_error) for d in invalid],
                        analysis_failures=[dict(revision_id=r.id, attempts=r.analysis_attempts, error=r.analysis_error) for r in failed_analysis],
                        runs=[dict(id=r.id, scope=r.scope, status=r.status, counts=r.counts, error=r.error,
                                   started_at=str(r.created_at), finished_at=str(r.finished_at)) for r in runs])
    finally:
        await dispose_engine()


if __name__ == "__main__":
    arguments = parser().parse_args()
    try:
        result = asyncio.run(run(arguments))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, dict) and result.get("failures"):
            raise SystemExit(2)
    except AuthenticationRequired:
        print("上游会话失效，需要重新导入现场登录材料；原进度已保留。", file=sys.stderr)
        raise SystemExit(78)
    except Exception as error:
        # Never emit HTTP exception URLs (upstream token is a query parameter).
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print(f"同步失败：{type(error).__name__}；已确认记录可从水位继续。", file=sys.stderr)
        raise SystemExit(1)
