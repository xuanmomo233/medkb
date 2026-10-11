from fastapi import APIRouter

from app.api.deps import AdminUser, Session
from app.schemas.admin import AdminQuestion, AdminQuestionPatch, ChangedOut
from app.services import quiz as admin_questions

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/questions/{qid}", response_model=AdminQuestion)
async def get_question(qid: int, session: Session, admin: AdminUser):
    return await admin_questions.get_question(session, qid)


@router.put("/questions/{qid}", response_model=ChangedOut)
async def put_question(qid: int, body: AdminQuestionPatch, session: Session, admin: AdminUser):
    return ChangedOut(changed=await admin_questions.update_question(session, admin.id, qid, body))
