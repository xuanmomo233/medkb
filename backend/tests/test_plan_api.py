import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from app.api import quiz, today
from app.api.deps import current_user
from app.core.db import get_session
from app.models import QuestionMerge, QuestionRelation, User
from test_plan_queue import seed


@pytest.mark.asyncio
async def test_plan_end_to_end_resume_sync_and_related_empty_contract(session):
    await seed(session)
    app = FastAPI()
    app.include_router(today.router, prefix="/api")
    app.include_router(quiz.router, prefix="/api")

    async def db():
        yield session

    app.dependency_overrides[get_session] = db
    app.dependency_overrides[current_user] = lambda: User(id=1, username="learner", password_hash="x")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.put("/api/plan/config", json={"total_days": 1, "items": [
            {"subject": "内科学", "part": "甲"}, {"subject": "内科学", "part": "乙"},
        ]})
        assert saved.status_code == 204
        state = (await client.get("/api/plan")).json()
        assert state["today_questions"] == 4 and state["scheduled_days"] == [1]
        first = (await client.get("/api/quiz/questions", params={"plan_day": 1})).json()
        assert len({q["id"] for q in first}) == 4
        assert (await client.post("/api/quiz/attempts", json={"question_id": 3, "picked": [1]})).status_code == 200
        resumed = (await client.get("/api/quiz/questions", params={"plan_day": 1})).json()
        assert {q["id"] for q in resumed} == {1, 2, 4}
        state = (await client.get("/api/plan")).json()
        assert state["today_questions"] == state["pending_questions"] == 3
        detail = (await client.get("/api/plan/days/1")).json()
        assert {qid for group in detail["question_groups"] for qid in group["ids"]} == {1, 2, 4}
        related = await client.get("/api/quiz/questions/1/related")
        assert related.status_code == 200 and related.json() == []
        assert (await client.get("/api/quiz/questions/999/related")).status_code == 404
        assert (await client.post("/api/plan/restart")).status_code == 204
        assert (await client.get("/api/plan")).json()["pending_questions"] == 3
    for model in (QuestionMerge, QuestionRelation):
        assert await session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.asyncio
async def test_related_requires_authentication():
    app = FastAPI()
    app.include_router(quiz.router, prefix="/api")

    async def db():
        yield None

    app.dependency_overrides[get_session] = db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/quiz/questions/1/related")).status_code == 401
