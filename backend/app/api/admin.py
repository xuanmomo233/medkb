import secrets

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AdminUser, Session
from app.models import InviteCode
from app.schemas.admin import AdminQuestion, AdminQuestionPatch, ChangedOut, InviteCreate, InviteOut, SiteConfigOut, SiteConfigPatch
from app.services import quiz as admin_questions
from app.services import study

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/questions/{qid}", response_model=AdminQuestion)
async def get_question(qid: int, session: Session, admin: AdminUser):
    return await admin_questions.get_question(session, qid)


@router.put("/questions/{qid}", response_model=ChangedOut)
async def put_question(qid: int, body: AdminQuestionPatch, session: Session, admin: AdminUser):
    return ChangedOut(changed=await admin_questions.update_question(session, admin.id, qid, body))


def _out(c: InviteCode) -> InviteOut:
    return InviteOut(
        code=c.code, created_by=c.created_by, used_by=c.used_by,
        used_at=c.used_at.isoformat() if c.used_at else None,
        created_at=c.created_at.isoformat() if c.created_at else None,
    )


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(session: Session, admin: AdminUser):
    rows = (await session.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))).scalars()
    return [_out(c) for c in rows]


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
