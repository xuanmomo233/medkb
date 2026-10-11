from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, Session
from app.schemas import quiz as S
from app.services import exam as exam_svc
from app.services import quiz as svc
from app.services.quiz_filters import QuizParams, parse_ids

router = APIRouter(prefix="/quiz", tags=["quiz"])


def quiz_params(
    bank_group: str = "", bank: str = "", subject_dir: str = "", system: str = "", chapter: str = "", qtype: str = "",
    ids: str | None = None, plan_day: int | None = None,
    starred: bool = False, wrong: bool = False, due: bool = False,
    random: bool = False, shuffle: bool = False, limit: int | None = None,
) -> QuizParams:
    return QuizParams(
        bank_group=bank_group, bank=bank, subject_dir=subject_dir, system=system, chapter=chapter, qtype=qtype,
        ids=parse_ids(ids), plan_day=plan_day, starred=starred, wrong=wrong, due=due,
        random=random, shuffle=shuffle, limit=limit if limit and limit > 0 else None,
    )


Params = Annotated[QuizParams, Depends(quiz_params)]


@router.get("/facets")
async def facets(
    session: Session, user: CurrentUser,
    bank_group: str = "", bank: str = "", subject_dir: str = "", system: str = "", chapter: str = "", qtype: str = "",
):
    p = QuizParams(bank_group=bank_group, bank=bank, subject_dir=subject_dir, system=system, chapter=chapter, qtype=qtype)
    return await svc.facets(session, user.id, p)


@router.get("/questions", response_model=list[S.QuestionOut])
async def questions(session: Session, user: CurrentUser, p: Params, lite: bool = False):
    return await svc.list_questions(session, user.id, p, lite)


@router.get("/questions/{qid}", response_model=S.QuestionFull)
async def question_full(qid: int, session: Session, user: CurrentUser):
    return await svc.question_full(session, user.id, qid)


@router.post("/questions/{qid}/ai-analysis", response_model=S.AiAnalysisOut)
async def ai_analysis(qid: int, session: Session, user: CurrentUser):
    return S.AiAnalysisOut(analysis_html=await svc.ai_analysis(session, user.id, qid))


@router.post("/attempts", response_model=S.AttemptResult)
async def attempt(body: S.AttemptIn, session: Session, user: CurrentUser):
    return await svc.attempt(session, user.id, body.question_id, body.picked)


@router.post("/submit", response_model=S.ExamReport, response_model_exclude_none=False)
async def submit(body: S.SubmitIn, session: Session, user: CurrentUser):
    return await exam_svc.submit(session, user.id, body.title, body.items)


@router.get("/mock", response_model=S.MockOut)
async def mock(session: Session, user: CurrentUser, n: int = 180):
    return S.MockOut(ids=await exam_svc.mock(session, n))


@router.get("/pool", response_model=S.PoolPage)
async def pool(
    session: Session, user: CurrentUser, p: Params,
    flt: str | None = None, offset: int = Query(0, ge=0), size: int = Query(50, ge=1, le=200),
):
    return await svc.pool(session, user.id, p, flt, offset, size)


@router.get("/wrongbook", response_model=list[S.WrongBookGroup])
async def wrongbook(session: Session, user: CurrentUser):
    return await svc.wrongbook(session, user.id)


@router.get("/exams", response_model=list[S.ExamRecord])
async def exams(session: Session, user: CurrentUser):
    return await exam_svc.exams(session, user.id)
