import hmac
import os
import re
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_token, verify_password
from app.models import AuthToken, User

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fa5]{2,24}$")
_FAIL_WINDOW = 300
_FAIL_LIMIT = 8
_fails: dict[str, list[float]] = {}


def _prune(key: str) -> list[float]:
    now = time.monotonic()
    lst = [t for t in _fails.get(key, []) if now - t < _FAIL_WINDOW]
    if lst:
        _fails[key] = lst
    else:
        _fails.pop(key, None)
    return lst


def _keys(username: str, ip: str) -> list[str]:
    return [f"u:{username.lower()}", f"ip:{ip}"]


def _check_rate(username: str, ip: str) -> None:
    for k in _keys(username, ip):
        if len(_prune(k)) >= _FAIL_LIMIT:
            raise HTTPException(429, "尝试次数过多，请 5 分钟后再试")


def _record_fail(username: str, ip: str) -> None:
    now = time.monotonic()
    for k in _keys(username, ip):
        _fails.setdefault(k, []).append(now)


def _clear_fail(username: str) -> None:
    _fails.pop(f"u:{username.lower()}", None)


async def _issue_token(session: AsyncSession, user: User, user_agent: str) -> str:
    token = new_token()
    session.add(
        AuthToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().token_ttl_days),
            user_agent=(user_agent or "")[:255],
        )
    )
    return token


async def register(session: AsyncSession, username: str, password: str, invite_code: str, user_agent: str):
    invite = get_settings().invite_code.get_secret_value()
    if invite and not hmac.compare_digest(invite.encode(), (invite_code or "").encode()):
        raise HTTPException(403, "邀请码错误")
    username = username.strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "用户名需为 2-24 位中英文、数字、下划线或短横线")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    exists = (await session.execute(select(User.id).where(User.username == username))).first()
    if exists:
        raise HTTPException(409, "用户名已被注册")
    user = User(username=username, password_hash=hash_password(password), is_admin=False)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "用户名已被注册")
    token = await _issue_token(session, user, user_agent)
    await session.commit()
    return token, user


async def login(session: AsyncSession, username: str, password: str, ip: str, user_agent: str):
    username = username.strip()
    _check_rate(username, ip)
    user = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        _record_fail(username, ip)
        raise HTTPException(401, "用户名或密码错误")
    _clear_fail(username)
    user.last_login_at = datetime.now(timezone.utc)
    token = await _issue_token(session, user, user_agent)
    await session.commit()
    return token, user


async def logout(session: AsyncSession, token: str) -> None:
    await session.execute(delete(AuthToken).where(AuthToken.token_hash == hash_token(token)))
    await session.commit()


def version_info() -> dict:
    raw = os.environ.get("MEDKB_VERSION", "2|MedKB v2")
    build_s, _, note = raw.partition("|")
    try:
        build = int(build_s.strip())
    except ValueError:
        build = 2
    return {"build": build, "note": note.strip() or "MedKB v2"}
