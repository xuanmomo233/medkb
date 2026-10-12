from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import hash_token
from app.models import AuthToken, User

Session = Annotated[AsyncSession, Depends(get_session)]


async def current_user(
    session: Session,
    x_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = x_token or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else "")
    if not token:
        raise HTTPException(401, "unauthorized")
    row = (
        await session.execute(
            select(AuthToken, User).join(User, User.id == AuthToken.user_id).where(AuthToken.token_hash == hash_token(token))
        )
    ).first()
    if row is None:
        raise HTTPException(401, "unauthorized")
    tok, user = row
    now = datetime.now(timezone.utc)
    exp = tok.expires_at if tok.expires_at.tzinfo else tok.expires_at.replace(tzinfo=timezone.utc)
    if exp < now:
        raise HTTPException(401, "token expired")
    lu = tok.last_used_at
    if lu is None or now - (lu if lu.tzinfo else lu.replace(tzinfo=timezone.utc)) > timedelta(minutes=10):
        tok.last_used_at = now
        await session.commit()
    return user


async def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(403, "admin only")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
