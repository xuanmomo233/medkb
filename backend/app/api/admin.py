import hashlib
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import delete, select

from app.api.deps import AdminUser, Session
from app.core.config import get_settings
from app.core.render import card_md, md
from app.core.security import verify_password
from app.models import InviteCode, QuestionEdit, User
from app.schemas.admin import (AdminCard, AdminCardPatch, AdminQuestion, AdminQuestionPatch, AdminUserDelete, AdminUserOut,
                               ChangedOut, InviteCreate, InviteOut, SiteConfigOut, SiteConfigPatch)
from app.schemas.admin import MarkdownPreviewIn, MarkdownPreviewOut
from app.services import cards as admin_cards
from app.services import quiz as admin_questions
from app.services import study

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/preview", response_model=MarkdownPreviewOut)
async def preview_markdown(body: MarkdownPreviewIn, admin: AdminUser):
    render = card_md if body.kind == "card" else md
    return MarkdownPreviewOut(html=render(body.text))

_DEL_FAIL_WINDOW = 300
_DEL_FAIL_LIMIT = 5
_del_fails: dict[int, list[float]] = {}


def _check_del_rate(admin_id: int) -> None:
    now = time.monotonic()
    lst = [t for t in _del_fails.get(admin_id, []) if now - t < _DEL_FAIL_WINDOW]
    if lst:
        _del_fails[admin_id] = lst
    else:
        _del_fails.pop(admin_id, None)
    if len(lst) >= _DEL_FAIL_LIMIT:
        raise HTTPException(429, "密码验证失败次数过多，请 5 分钟后再试")


def _record_del_fail(admin_id: int) -> None:
    _del_fails.setdefault(admin_id, []).append(time.monotonic())


@router.get("/questions/{qid}", response_model=AdminQuestion)
async def get_question(qid: int, session: Session, admin: AdminUser):
    return await admin_questions.get_question(session, qid)


@router.put("/questions/{qid}", response_model=ChangedOut)
async def put_question(qid: int, body: AdminQuestionPatch, session: Session, admin: AdminUser):
    return ChangedOut(changed=await admin_questions.update_question(session, admin.id, qid, body))


@router.get("/cards/{card_id}", response_model=AdminCard)
async def get_card(card_id: int, session: Session, admin: AdminUser):
    return await admin_cards.get_admin_card(session, card_id)


@router.put("/cards/{card_id}", response_model=ChangedOut)
async def put_card(card_id: int, body: AdminCardPatch, session: Session, admin: AdminUser):
    return ChangedOut(changed=await admin_cards.update_admin_card(session, card_id, body))


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(session: Session, admin: AdminUser, q: str = "", invite: str = ""):
    stmt = select(User).order_by(User.id)
    if q.strip():
        stmt = stmt.where(User.username.contains(q.strip(), autoescape=True))
    if invite.strip():
        stmt = (stmt.join(InviteCode, InviteCode.used_by == User.id)
                    .where(InviteCode.code == invite.strip()))
    users = (await session.execute(stmt)).scalars().all()
    codes = {c.used_by: c.code for c in (await session.execute(
        select(InviteCode).where(InviteCode.used_by.is_not(None)))).scalars()}
    return [
        AdminUserOut(
            id=u.id, username=u.username, is_admin=u.is_admin,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            invite_code=codes.get(u.id),
        )
        for u in users
    ]


@router.delete("/users/{uid}", status_code=204)
async def delete_user(uid: int, body: AdminUserDelete, session: Session, admin: AdminUser):
    if uid == admin.id:
        raise HTTPException(400, "不能删除当前登录的管理员账号")
    target = await session.get(User, uid)
    if target is None:
        raise HTTPException(404, "用户不存在")
    if target.is_admin:
        raise HTTPException(409, "不能删除管理员账号")
    _check_del_rate(admin.id)
    if not verify_password(body.password, admin.password_hash):
        _record_del_fail(admin.id)
        raise HTTPException(403, "管理员密码错误")
    _del_fails.pop(admin.id, None)
    # question_edits 外键无级联，先人工清
    await session.execute(delete(QuestionEdit).where(QuestionEdit.user_id == uid))
    await session.delete(target)
    await session.commit()


def _out(c: InviteCode, names: dict[int, str] | None = None) -> InviteOut:
    return InviteOut(
        code=c.code, created_by=c.created_by, used_by=c.used_by,
        used_by_username=(names or {}).get(c.used_by) if c.used_by is not None else None,
        used_at=c.used_at.isoformat() if c.used_at else None,
        created_at=c.created_at.isoformat() if c.created_at else None,
    )


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(session: Session, admin: AdminUser):
    rows = (await session.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))).scalars().all()
    uids = {c.used_by for c in rows if c.used_by is not None}
    names = {}
    if uids:
        names = {u.id: u.username for u in (await session.execute(
            select(User).where(User.id.in_(uids)))).scalars()}
    return [_out(c, names) for c in rows]


@router.post("/invites", response_model=list[InviteOut], status_code=201)
async def create_invites(body: InviteCreate, session: Session, admin: AdminUser):
    if not 1 <= body.count <= 50:
        raise HTTPException(400, "count 需在 1-50")
    rows = [
        InviteCode(code=secrets.token_urlsafe(9), created_by=admin.id)
        for _ in range(body.count)
    ]
    session.add_all(rows)
    await session.commit()
    return [_out(c) for c in rows]


@router.delete("/invites/{code}", status_code=204)
async def revoke_invite(code: str, session: Session, admin: AdminUser):
    row = (await session.execute(select(InviteCode).where(InviteCode.code == code))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "邀请码不存在")
    if row.used_by is not None:
        raise HTTPException(409, "已被使用，不可撤销")
    await session.delete(row)
    await session.commit()


_IMG_MAX = 6 * 1024 * 1024


def _img_ext(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post("/images", status_code=201)
async def upload_image(admin: AdminUser, file: UploadFile):
    """管理员上传题目配图（App 端 /api/admin/images）：魔数校验 + sha1 命名存 uimg。"""
    data = await file.read(_IMG_MAX + 1)
    if len(data) > _IMG_MAX:
        raise HTTPException(413, "图片过大（最大 6MB）")
    ext = _img_ext(data)
    if ext is None:
        raise HTTPException(415, "仅支持 png/jpg/webp/gif")
    name = hashlib.sha1(data).hexdigest()[:16] + ext
    d = Path(get_settings().upload_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(data)
    except OSError:
        raise HTTPException(500, "图片保存失败")
    return {"url": f"/uimg/{name}"}


@router.get("/site", response_model=SiteConfigOut)
async def get_site(session: Session, admin: AdminUser):
    return SiteConfigOut(exam_date=(await study.get_exam_date(session)).isoformat())


@router.put("/site", response_model=SiteConfigOut)
async def put_site(body: SiteConfigPatch, session: Session, admin: AdminUser):
    try:
        d = await study.set_exam_date(session, body.exam_date)
    except ValueError:
        raise HTTPException(400, "日期格式应为 YYYY-MM-DD")
    return SiteConfigOut(exam_date=d.isoformat())
