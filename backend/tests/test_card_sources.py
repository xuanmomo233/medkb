import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from app.api.cards import router
from app.api.deps import current_user
from app.core.db import get_session
from app.models import Attempt, Card, CardMerge, QuestionProgress, User
from test_plan_queue import seed


@pytest.mark.asyncio
async def test_sources_route_is_read_only_and_preserves_study_history(session):
    await seed(session)
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def db():
        yield session

    app.dependency_overrides[get_session] = db
    app.dependency_overrides[current_user] = lambda: User(id=1, username="learner", password_hash="x")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/cards/10/sources")
        assert response.status_code == 200
        sources = response.json()
        assert [q["id"] for q in sources] == [1, 3]
        assert sources[1]["parent_html"] and sources[1]["options_html"]
        for source in sources:
            assert {"id", "qid", "system", "stem_html", "answer", "analysis_html"}.issubset(source)
            assert source["analysis_html"]
        assert (await client.get("/api/cards/999/sources")).status_code == 404
        session.add(Card(id=12, subject="内科学", part="甲", term="无源题", body=""))
        await session.commit()
        response = await client.get("/api/cards/12/sources")
        assert response.status_code == 200 and response.json() == []
        session.add(CardMerge(alias_id=11, canonical_id=10, batch_id="test"))
        await session.commit()
        for cid in (10, 11):
            assert [q["id"] for q in (await client.get(f"/api/cards/{cid}/sources")).json()] == [1, 2, 3]
    assert await session.scalar(select(func.count()).select_from(Attempt)) == 0
    assert await session.scalar(select(func.count()).select_from(QuestionProgress)) == 0


@pytest.mark.asyncio
async def test_card_sources_requires_login():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def db():
        yield None

    app.dependency_overrides[get_session] = db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/cards/10/sources")).status_code == 401


@pytest.mark.asyncio
async def test_source_answer_updates_plan_and_pool_while_mastery_and_reading_do_not(session):
    from app.api import quiz, today, progress

    await seed(session)
    app = FastAPI()
    for routes in (router, quiz.router, today.router, progress.router):
        app.include_router(routes, prefix="/api")

    async def db():
        yield session

    app.dependency_overrides[get_session] = db
    app.dependency_overrides[current_user] = lambda: User(id=1, username="learner", password_hash="x")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.put("/api/plan/config", json={"total_days": 1, "items": [
            {"subject": "内科学", "part": "甲"}, {"subject": "内科学", "part": "乙"},
        ]})
        await client.get("/api/cards/10/sources")
        await client.get("/api/quiz/questions/1")  # Reading an explanation is not an answer.
        await client.post("/api/progress/mark", json={"target_type": "question", "target_id": 1, "action": "master"})
        state = (await client.get("/api/plan")).json()
        assert state["pending_questions"] == 4
        pool = (await client.get("/api/quiz/pool")).json()
        assert pool["stats"]["done"] == 0 and pool["stats"]["mastered"] == 1
        todo = (await client.get("/api/quiz/pool", params={"flt": "todo"})).json()
        assert 1 in [item["id"] for item in todo["items"]]
        assert (await client.get("/api/quiz/pool", params={"flt": "done"})).json()["items"] == []
        assert (await client.get("/api/today")).json()["done_today"] == 0
        assert (await client.post("/api/quiz/attempts", json={"question_id": 1, "picked": [1]})).json()["correct"] is False
        state = (await client.get("/api/plan")).json()
        assert state["pending_questions"] == 3
        assert all(item["question_done"] == 1 for item in state["items"])
        pending = (await client.get("/api/quiz/questions", params={"plan_day": 1})).json()
        assert 1 not in [item["id"] for item in pending]
        source = (await client.get("/api/cards/10/sources")).json()[0]
        assert source["done"] is True
        pool = (await client.get("/api/quiz/pool")).json()
        assert pool["stats"]["done"] == 1
        assert (await client.get("/api/today")).json()["done_today"] == 1
