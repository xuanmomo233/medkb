from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router
from app.api.deps import current_user
from app.core.db import get_session


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def unused_session():
        yield None

    app.dependency_overrides[get_session] = unused_session
    return app


def test_preview_needs_authentication(app):
    with TestClient(app) as client:
        assert client.post("/api/admin/preview", json={"text": "test"}).status_code == 401


def test_preview_requires_admin(app):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=False)
    with TestClient(app) as client:
        assert client.post("/api/admin/preview", json={"text": "test"}).status_code == 403


def test_preview_renders_without_database_writes(app):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=True)
    with TestClient(app) as client:
        out = client.post("/api/admin/preview", json={"text": "==重点== <script>alert(1)</script>"})
        assert out.status_code == 200
        assert '<mark class="manual">重点</mark>' in out.json()["html"]
        assert "alert(1)" not in out.json()["html"]
        card = client.post("/api/admin/preview", json={"text": "甲；乙；丙", "kind": "card"})
        assert "<li>" in card.json()["html"]
        assert client.post("/api/admin/preview", json={"text": "x", "kind": "invalid"}).status_code == 422
        assert client.post("/api/admin/preview", json={"text": "😀" * 20000}).status_code == 200
        assert client.post("/api/admin/preview", json={"text": "😀" * 20001}).status_code == 422
