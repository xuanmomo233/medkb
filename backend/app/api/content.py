from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, Session
from app.schemas.content import ChapterDetail, ContentTree, SearchHit
from app.services import content as svc

router = APIRouter(tags=["content"])


@router.get("/content/tree", response_model=ContentTree)
async def tree(session: Session, user: CurrentUser):
    return await svc.tree(session)


@router.get("/content/chapters/{chapter_id}", response_model=ChapterDetail)
async def chapter(chapter_id: int, session: Session, user: CurrentUser):
    d = await svc.chapter_detail(session, chapter_id)
    if d is None:
        raise HTTPException(404, "章节不存在")
    return d


@router.get("/search", response_model=list[SearchHit])
async def search(
    session: Session,
    user: CurrentUser,
    q: Annotated[str, Query(max_length=200)] = "",
    kind: Literal["question", "card", "chapter"] | None = None,
):
    return await svc.search(session, user.id, q, kind)
