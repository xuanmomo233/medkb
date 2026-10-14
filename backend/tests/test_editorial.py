from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.admin import router
from app.api.deps import current_user
from app.core.db import get_session
from app.models import Card, User
from app.schemas.editorial import ReviewDecisionIn
from app.services import editorial


def test_catalog_id_is_stable_across_windows_line_endings(tmp_path, monkeypatch):
    editorial.catalog.cache_clear()
    expected_id, _, original_items = editorial.catalog()
    raw = editorial.DATA_PATH.read_bytes().replace(b"\r\n", b"\n")
    alternative = tmp_path / "editorial_review.json"
    alternative.write_bytes(raw.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(editorial, "DATA_PATH", alternative)
    editorial.catalog.cache_clear()
    try:
        dataset_id, _, items = editorial.catalog()
        assert dataset_id == expected_id
        assert items == original_items
    finally:
        editorial.catalog.cache_clear()


@pytest.mark.parametrize("path,method", [
    ("/api/admin/reviews", "get"),
    ("/api/admin/reviews/MECH-01", "get"),
    ("/api/admin/reviews/MECH-01/decision", "put"),
])
def test_review_authentication_and_admin_role(path, method):
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def unused_session():
        yield None

    app.dependency_overrides[get_session] = unused_session
    with TestClient(app) as client:
        assert getattr(client, method)(path).status_code == 401
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=False)
        assert getattr(client, method)(path).status_code == 403


@pytest.mark.asyncio
async def test_catalog_filters_paging_and_admin_content(session):
    result = await editorial.list_items(session, "exact", "", "", 0, 20)
    assert result["total"] == 3
    assert result["counts"]["mechanisms"] == 5
    assert result["counts"]["overlap"] == 8
    assert len((await editorial.list_items(session, "", "", "", 0, 20))["items"]) == 20
    match = await editorial.list_items(session, "", "", "2870", 0, 20)
    assert any(2870 in i["card_ids"] for i in match["items"])
    detail = await editorial.detail(session, "MECH-01")
    assert "动脉压上升" in detail["proposal_html"]
    assert detail["sources"] and detail["cards"] and detail["executed"] is False
    assert detail["cards"][0]["current"] is None
    assert detail["cards"][0]["changed"] is True
    for item in editorial.catalog()[2]:
        assert (await editorial.detail(session, item))["id"] == item
    with pytest.raises(HTTPException) as error:
        await editorial.detail(session, "not-a-review")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_decisions_persist_without_changing_cards_and_reject_stale_writes(session):
    _, _, items = editorial.catalog()
    item = next(i for i in items.values() if i["category"] == "exact")
    original = item["cards"][0]
    session.add_all([User(id=1, username="local-test-admin", password_hash="unused", is_admin=True), Card(**original)])
    await session.commit()
    before = dict((await editorial.detail(session, item["id"]))["cards"][0]["current"])
    result = await editorial.save_decision(session, 1, item["id"], ReviewDecisionIn(
        status="approved", note="先保留原卡，只认可审核方案。", expected_version=0))
    assert result["version"] == 1 and result["status"] == "approved"
    assert (await editorial.detail(session, item["id"]))["cards"][0]["current"] == before
    filtered = await editorial.list_items(session, "exact", "approved", "", 0, 20)
    assert filtered["total"] == 1
    with pytest.raises(HTTPException) as error:
        await editorial.save_decision(session, 1, item["id"], ReviewDecisionIn(status="rejected", expected_version=0))
    assert error.value.status_code == 409
    result = await editorial.save_decision(session, 1, item["id"], ReviewDecisionIn(status="needs_revision", expected_version=1))
    assert result["version"] == 2
    with pytest.raises(HTTPException) as error:
        await editorial.save_decision(session, 1, item["id"], ReviewDecisionIn(status="approved", expected_version=1))
    assert error.value.status_code == 409
    card = await session.get(Card, original["id"])
    card.hint = "手工更新后的提示"
    await session.commit()
    assert (await editorial.detail(session, item["id"]))["cards"][0]["changed"] is True


def test_decision_validation():
    with pytest.raises(ValidationError):
        ReviewDecisionIn(status="delete", expected_version=0)
    with pytest.raises(ValidationError):
        ReviewDecisionIn(status="pending", note="x" * 4001, expected_version=0)
