from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import files
from app.api.deps import current_user
from app.models import TextbookSource


@pytest.fixture
def app(tmp_path, monkeypatch):
    textbook_dir = tmp_path / "textbooks"
    source_dir = textbook_dir / "rjws-pathology-10"
    source_dir.mkdir(parents=True)
    (source_dir / "page_0005.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    textbook_pdf_dir = tmp_path / "textbook-pdfs"
    textbook_pdf_dir.mkdir()
    pdf_bytes = b"%PDF-1.7\n0123456789abcdef\n%%EOF"
    (textbook_pdf_dir / "rjws-pathology-10.pdf").write_bytes(pdf_bytes)
    monkeypatch.setattr(files, "get_settings", lambda: SimpleNamespace(
        textbook_img_dir=str(textbook_dir), textbook_pdf_dir=str(textbook_pdf_dir),
    ))
    value = FastAPI()
    value.include_router(files.router)
    def unauthenticated():
        raise HTTPException(401, "unauthorized")
    value.dependency_overrides[current_user] = unauthenticated
    value.dependency_overrides[files.active_textbook_source] = lambda source_key: source_key
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


def test_textbook_pdf_requires_login_and_supports_private_range_reads(app):
    with TestClient(app) as client:
        assert client.get("/api/textbooks/rjws-pathology-10.pdf").status_code == 401
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1)
        response = client.get(
            "/api/textbooks/rjws-pathology-10.pdf",
            headers={"Range": "bytes=0-7"},
        )
        assert response.status_code == 206
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.headers["content-range"] == "bytes 0-7/31"
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-disposition"] == "inline"
        assert response.content == b"%PDF-1.7"


async def test_textbook_pdf_source_must_be_registered_and_active(session):
    session.add(TextbookSource(
        key="rjws-pathology-10", title="病理学", subject="病理学",
        publisher="人民卫生出版社", edition="第十版", active=True,
    ))
    await session.commit()
    assert await files.active_textbook_source("rjws-pathology-10", session) == "rjws-pathology-10"

    with pytest.raises(HTTPException) as missing:
        await files.active_textbook_source("rjws-unknown-10", session)
    assert missing.value.status_code == 404

    with pytest.raises(HTTPException) as malformed:
        await files.active_textbook_source("../img", session)
    assert malformed.value.status_code == 404

    await session.execute(
        TextbookSource.__table__.update()
        .where(TextbookSource.key == "rjws-pathology-10")
        .values(active=False)
    )
    with pytest.raises(HTTPException) as inactive:
        await files.active_textbook_source("rjws-pathology-10", session)
    assert inactive.value.status_code == 404
