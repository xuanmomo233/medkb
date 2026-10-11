from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from app.api.deps import CurrentUser, Session
from app.schemas.notes import LikeOut, NoteCreate, NoteOut, PublicNoteOut
from app.services import notes as svc

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut], response_model_exclude_none=True)
async def my_notes(
    session: Session, user: CurrentUser,
    target_type: Literal["question", "card"] | None = None, target_id: int | None = None,
):
    return await svc.list_for_target(session, user.id, target_type, target_id)


@router.get("/mine", response_model=list[NoteOut])
async def mine(session: Session, user: CurrentUser):
    return await svc.list_mine(session, user.id)


@router.get("/public", response_model=list[PublicNoteOut])
async def public(session: Session, user: CurrentUser, target_type: Literal["question", "card"], target_id: int):
    return await svc.list_public(session, user.id, target_type, target_id)


@router.post("", status_code=204)
async def create(body: NoteCreate, session: Session, user: CurrentUser) -> Response:
    if not await svc.create(session, user.id, body.target_type, body.target_id, body.body, body.is_public):
        raise HTTPException(404, "目标不存在")
    return Response(status_code=204)


@router.delete("/{note_id}", status_code=204)
async def delete(note_id: int, session: Session, user: CurrentUser) -> Response:
    if not await svc.delete_own(session, user.id, note_id):
        raise HTTPException(404, "笔记不存在")
    return Response(status_code=204)


@router.post("/{note_id}/like", response_model=LikeOut)
async def like(note_id: int, session: Session, user: CurrentUser):
    r = await svc.toggle_like(session, user.id, note_id)
    if r is None:
        raise HTTPException(404, "公开笔记不存在")
    return r
