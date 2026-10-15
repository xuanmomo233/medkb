from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import files
from app.api.deps import current_user


@pytest.fixture
def app(tmp_path, monkeypatch):
    textbook_dir = tmp_path / "textbooks"
    source_dir = textbook_dir / "rjws-pathology-10"
    source_dir.mkdir(parents=True)
    (source_dir / "page_0005.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    monkeypatch.setattr(files, "get_settings", lambda: SimpleNamespace(textbook_img_dir=str(textbook_dir)))
    value = FastAPI()
    value.include_router(files.router)
    def unauthenticated():
        raise HTTPException(401, "unauthorized")
    value.dependency_overrides[current_user] = unauthenticated
    return value


def test_textbook_image_requires_login_and_is_not_cacheable(app):
    with TestClient(app) as client:
        assert client.get("/api/textbook-images/rjws-pathology-10/5.webp").status_code == 401
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1)
        response = client.get("/api/textbook-images/rjws-pathology-10/5.webp")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/webp")
        assert response.headers["cache-control"] == "private, no-store"


def test_textbook_image_rejects_invalid_source_and_missing_page(app):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1)
    with TestClient(app) as client:
        assert client.get("/api/textbook-images/../img/5.webp").status_code == 404
        assert client.get("/api/textbook-images/rjws-pathology-10/6.webp").status_code == 404
