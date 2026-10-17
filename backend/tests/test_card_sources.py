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
async def test_sources_route_supports_legacy_client_and_preserves_study_history(session):
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
