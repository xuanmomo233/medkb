from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import current_user
from app.api.quiz import router
from app.core.db import get_session
from app.models import Attempt, Question, User


async def test_http_labels_and_submitted_positions_round_trip_without_rewriting_source(session):
    labels = list("ABCDEFGHJK")
    source = Question(id=1, qid="synthetic-label-http", stem="合成题干",
                      options=[f"选项{letter}" for letter in labels],
                      option_labels=labels, answer="Ｊ、Ｋ", qtype="多选")
    user = User(id=7, username="label-http", password_hash="unused")
    session.add_all([source, user])
    await session.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def isolated_session():
        yield session

    app.dependency_overrides[get_session] = isolated_session
    app.dependency_overrides[current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/quiz/questions", params={"ids": "1", "lite": True})
        assert listed.status_code == 200
        assert listed.json()[0]["option_labels"] == labels
        detail = await client.get("/api/quiz/questions/1")
        assert detail.status_code == 200
        assert detail.json()["option_labels"] == labels
        assert len(detail.json()["options_html"]) == 10
        practice = await client.post("/api/quiz/attempts", json={"question_id": 1, "picked": [8, 9]})
        assert practice.status_code == 200 and practice.json()["correct"] is True
        exam = await client.post("/api/quiz/submit", json={
            "title": "合成标签模考", "items": [{"question_id": 1, "picked": [8, 9]}]})
        assert exam.status_code == 200 and exam.json()["correct"] == exam.json()["total"] == 1
        invalid = await client.post("/api/quiz/attempts", json={"question_id": 1, "picked": [10]})
        assert invalid.status_code == 400
    attempts = (await session.scalars(select(Attempt).order_by(Attempt.id))).all()
    assert [a.picked for a in attempts] == ["JK", "JK"]
    await session.refresh(source)
    assert source.answer == "Ｊ、Ｋ" and source.option_labels == labels
