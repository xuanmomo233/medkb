from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, Session
from app.schemas.content import ChapterDetail, ContentTree, SearchHit, TextbookCatalog
from app.schemas.provenance import CitationTarget, ContentCitationOut
from app.services import content as svc
from app.services import provenance

router = APIRouter(tags=["content"])


@router.get("/content/tree", response_model=ContentTree)
async def tree(session: Session, user: CurrentUser):
    return await svc.tree(session)


@router.get("/content/textbooks", response_model=TextbookCatalog)
async def textbooks(session: Session, user: CurrentUser):
    return TextbookCatalog(sources=await provenance.list_sources(session))


@router.get("/content/{target_type}/{target_id}/citations", response_model=list[ContentCitationOut])
async def citations(target_type: CitationTarget, target_id: int, session: Session, user: CurrentUser):
    model = provenance.TARGET_MODELS[target_type]
    if await session.get(model, target_id) is None:
        raise HTTPException(404, "内容不存在")
    return await provenance.citations_for_target(session, target_type, target_id)


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
