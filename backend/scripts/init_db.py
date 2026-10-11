import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.models import Base  # noqa: E402


async def main() -> None:
    url = os.environ.get("MEDKB_DATABASE_URL")
    if not url:
        from app.core.config import get_settings
        url = get_settings().database_url
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"已建表 {len(Base.metadata.tables)} 张")


if __name__ == "__main__":
    asyncio.run(main())
