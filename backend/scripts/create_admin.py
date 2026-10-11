"""创建/提升管理员账号。用法: python scripts/create_admin.py <用户名> <密码>"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.models import User  # noqa: E402


async def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("用法: python scripts/create_admin.py <用户名> <密码>")
    username, password = sys.argv[1], sys.argv[2]
    url = os.environ.get("MEDKB_DATABASE_URL") or __import__("app.core.config", fromlist=["get_settings"]).get_settings().database_url
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine)
    async with sm() as s:
        user = (await s.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            s.add(User(username=username, password_hash=hash_password(password), is_admin=True))
            print(f"已创建管理员 {username}")
        else:
            user.password_hash = hash_password(password)
            user.is_admin = True
            print(f"{username} 已存在：已重置密码并设为管理员")
        await s.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
