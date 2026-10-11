from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api.deps import CurrentUser, Session
from app.schemas.auth import AuthResult, LoginBody, PasswordChange, RegisterBody, UserOut, VersionInfo
from app.services import auth as svc

router = APIRouter()


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/auth/register", response_model=AuthResult)
async def register(body: RegisterBody, session: Session, request: Request):
    token, user = await svc.register(
        session, body.username, body.password, body.invite_code, request.headers.get("user-agent", "")
    )
    return AuthResult(token=token, user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=AuthResult)
async def login(body: LoginBody, session: Session, request: Request):
    token, user = await svc.login(
        session, body.username, body.password, _ip(request), request.headers.get("user-agent", "")
    )
    return AuthResult(token=token, user=UserOut.model_validate(user))


@router.post("/auth/logout", status_code=204)
async def logout(
    user: CurrentUser,
    session: Session,
    x_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    token = x_token or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else "")
    if not token:
        raise HTTPException(401, "unauthorized")
    await svc.logout(session, token)
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.put("/auth/password", status_code=204)
async def change_password(
    body: PasswordChange,
    user: CurrentUser,
    session: Session,
    x_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    token = x_token or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else "")
    await svc.change_password(session, user, body.old_password, body.new_password, token)
    return Response(status_code=204)


@router.get("/version", response_model=VersionInfo)
async def version():
    return svc.version_info()
