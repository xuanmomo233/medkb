import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import dispose_engine, get_engine  # noqa: E402
from app.services.editorial_apply import apply, rollback  # noqa: E402


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan")
    parser.add_argument("--rollback")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if bool(args.plan) == bool(args.rollback):
        parser.error("指定 --plan 或 --rollback 之一")
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        try:
            result = await rollback(session, args.rollback) if args.rollback else await apply(
                session, json.loads(Path(args.plan).read_text(encoding="utf-8")),
            )
            if args.dry_run:
                await session.rollback()
                result["dry_run"] = True
            else:
                await session.commit()
            print(json.dumps(result, ensure_ascii=False))
        except Exception:
            await session.rollback()
            raise
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
