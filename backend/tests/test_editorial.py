from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.admin import router
from app.api.deps import current_user
from app.core.db import get_session
from app.models import Card, EditorialExecution, EditorialReview, User
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


@pytest.mark.parametrize("review_status,review_version,execution_status,execution_version,expected", [
    (None, 0, "merged", 0, "completed"),
    (None, 0, "kept", 0, "completed"),
    (None, 0, None, 0, "needs_review"),
    ("pending", 1, "deferred", 1, "needs_review"),
    ("pending", 2, "merged", 1, "needs_review"),
    ("approved", 2, "deferred", 1, "waiting_execution"),
    ("needs_revision", 2, "merged", 1, "waiting_execution"),
    ("rejected", 2, "merged", 1, "waiting_execution"),
    ("approved", 2, "merged", 2, "completed"),
    ("rejected", 1, "unchanged", 1, "completed"),
    ("approved", 1, "rolled_back", 1, "waiting_execution"),
    ("pending", 1, "unknown_status", 1, "needs_review"),
])
def test_review_work_queue(review_status, review_version, execution_status, execution_version, expected):
    review = SimpleNamespace(status=review_status, version=review_version) if review_status else None
    execution = SimpleNamespace(status=execution_status, review_version=execution_version) if execution_status else None
    assert editorial.review_queue(review, execution) == expected


@pytest.mark.asyncio
async def test_work_queue_filters_counts_paging_and_saved_reviews(session, monkeypatch):
    dataset = "work-queue-test"
    fixtures = [
        (None, 0, "merged", 0), ("pending", 1, "deferred", 1),
        ("approved", 2, "deferred", 1), ("approved", 2, "merged", 1),
        ("pending", 2, "merged", 1), ("approved", 2, "merged", 2),
        (None, 0, None, 0), ("rejected", 1, "unchanged", 1),
        ("needs_revision", 1, "rolled_back", 1),
    ]
    items = {}
    for index, (review_status, version, execution_status, applied_version) in enumerate(fixtures):
        ident = f"TEST-{index}"
        items[ident] = dict(id=ident, category="titles", title=ident, subjects=["内科学"], card_ids=[])
        if review_status:
            session.add(EditorialReview(key=dataset + ":" + ident, status=review_status, version=version))
        if execution_status:
            session.add(EditorialExecution(key=dataset + ":" + ident, review_version=applied_version,
                                           status=execution_status, description="test", batch_id="test"))
    session.add(User(id=1, username="queue-test-admin", password_hash="unused", is_admin=True))
    await session.commit()
    monkeypatch.setattr(editorial, "catalog", lambda: (dataset, "test-date", items))
    pending = await editorial.list_items(session, "", "", "", 0, 20, "needs_review")
    assert {i["id"] for i in pending["items"]} == {"TEST-1", "TEST-4", "TEST-6"}
    assert pending["counts"] == {"titles": 3}
    assert pending["queue_counts"] == dict(needs_review=3, waiting_execution=3, completed=3, all=9)
    assert all(i["work_queue"] == "needs_review" for i in pending["items"])
    page = await editorial.list_items(session, "", "", "", 1, 1, "needs_review")
    assert [i["id"] for i in page["items"]] == ["TEST-4"]
    empty = await editorial.list_items(session, "exact", "", "", 0, 20, "needs_review")
    assert empty["total"] == 0 and empty["counts"] == {"titles": 3}
    match = await editorial.list_items(session, "", "", "TEST-1", 0, 20, "needs_review")
    assert match["total"] == 1 and match["counts"] == {"titles": 1}
    await editorial.save_decision(session, 1, "TEST-1", ReviewDecisionIn(
        status="approved", note="已核对，等待执行", expected_version=1))
    remaining = await editorial.list_items(session, "", "", "", 0, 20, "needs_review")
    waiting = await editorial.list_items(session, "", "", "", 0, 20, "waiting_execution")
    assert remaining["total"] == 2 and waiting["total"] == 4
    assert "TEST-1" not in {i["id"] for i in remaining["items"]}
    assert "TEST-1" in {i["id"] for i in waiting["items"]}
    execution = await session.get(EditorialExecution, dataset + ":TEST-1")
    assert execution.status == "deferred" and execution.review_version == 1


def test_work_queue_query_validation():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def unused_session():
        yield None

    app.dependency_overrides[get_session] = unused_session
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=True)
    with TestClient(app) as client:
        assert client.get("/api/admin/reviews?queue=invalid").status_code == 422
