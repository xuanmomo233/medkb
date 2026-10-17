from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, Session
from app.schemas.cards import CardOut, CardPartIndex
from app.schemas.quiz import QuestionOut
from app.services import cards as svc

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/index", response_model=list[CardPartIndex])
async def index(session: Session, user: CurrentUser):
    return await svc.index(session)


@router.get("/{card_id}/sources", response_model=list[QuestionOut])
async def card_sources(card_id: int, session: Session, user: CurrentUser):
    return await svc.sources(session, user.id, card_id)


@router.get("", response_model=list[CardOut])
async def cards(
    session: Session,
    user: CurrentUser,
    subject: str | None = None,
    part: str | None = None,
    ids: str | None = None,
    plan_day: Annotated[int | None, Query(ge=0)] = None,
    starred: bool = False,
    due: bool = False,
):
    id_list = None
    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(422, "ids 格式错误，应为逗号分隔的整数")
        if not id_list:
            return []
    return await svc.list_cards(
        session, user.id, subject=subject, part=part, ids=id_list, plan_day=plan_day, starred=starred, due=due
    )
