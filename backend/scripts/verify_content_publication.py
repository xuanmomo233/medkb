"""核对教材书目、结构化出处和 AI 数据库发布链路。"""

import asyncio
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db import get_engine
from app.models import Card, Chapter, ContentCitation, Question, TextbookSource
from app.services.provenance import DEFAULT_TEXTBOOKS, TARGET_MODELS


async def main() -> None:
    failures: list[str] = []
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        source_rows = (await session.execute(select(TextbookSource))).scalars().all()
        source_keys = {row.key for row in source_rows}
        expected = {row["key"] for row in DEFAULT_TEXTBOOKS}
        missing = sorted(expected - source_keys)
        if missing:
            failures.append("缺少默认教材书目: " + ", ".join(missing))

        citations = (await session.execute(select(ContentCitation))).scalars().all()
        status_counts = Counter(row.status for row in citations)
        for row in citations:
            model = TARGET_MODELS.get(row.target_type)
            if model is None or await session.get(model, row.target_id) is None:
                failures.append(f"孤立出处 #{row.id}: {row.target_type}/{row.target_id}")
            if row.status in ("verified", "disputed") and (row.verified_by is None or row.verified_at is None):
                failures.append(f"核验信息不完整 #{row.id}")
            if row.status == "unverified" and (row.verified_by is not None or row.verified_at is not None):
                failures.append(f"待核验记录不应含核验人或时间 #{row.id}")

        counts = {
            "chapters": await session.scalar(select(func.count()).select_from(Chapter)),
            "questions": await session.scalar(select(func.count()).select_from(Question)),
            "cards": await session.scalar(select(func.count()).select_from(Card)),
            "textbooks": len(source_rows),
            "citations": len(citations),
            "verified": status_counts["verified"],
            "unverified": status_counts["unverified"],
            "disputed": status_counts["disputed"],
        }
    print(" ".join(f"{key}={value}" for key, value in counts.items()))
    if failures:
        for failure in failures:
            print("ERROR", failure)
        raise SystemExit(1)
    print("content publication verification passed")


if __name__ == "__main__":
    asyncio.run(main())
