from fastapi import APIRouter, HTTPException, Response

from app.api.deps import CurrentUser, Session
from app.schemas.progress import MarkBody
from app.services import progress as svc

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("/mark", status_code=204)
async def mark(body: MarkBody, session: Session, user: CurrentUser) -> Response:
    if not await svc.mark(session, user.id, body.target_type, body.target_id, body.action):
        raise HTTPException(404, "目标不存在")
    return Response(status_code=204)
