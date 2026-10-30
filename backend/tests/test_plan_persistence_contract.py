import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models import PlanTask, PlanTaskSection
from app.services import plan_queue


@pytest.mark.asyncio
async def test_user_scoped_reconciliation_preserves_target_due_and_completion_contract():
    completed = dt.datetime(2026, 10, 4, 12, 30, tzinfo=dt.timezone.utc)
    root = PlanTask(
        id=10, user_id=1, kind="question", target_id=1, position=4,
        due_day=dt.date(2026, 10, 5), completed_at=None,
    )
    equivalent = PlanTask(
        id=20, user_id=1, kind="question", target_id=2, position=2,
        due_day=dt.date(2026, 10, 3), completed_at=completed,
    )
    links = [
        PlanTaskSection(task_id=10, subject="内科学", part="甲"),
        PlanTaskSection(task_id=20, subject="内科学", part="乙"),
    ]
    session = SimpleNamespace(add=Mock(), flush=AsyncMock(), execute=AsyncMock())

    tasks, merged_links = await plan_queue._canonicalize_questions(
        session, [root, equivalent], links, mapping={2: 1},
    )

    assert tasks == [root]
    assert root.target_id == 1
    assert root.position == 2
    assert root.due_day == dt.date(2026, 10, 3)
    assert root.completed_at == completed
    assert {(link.subject, link.part) for link in merged_links} == {
        ("内科学", "甲"), ("内科学", "乙"),
    }
    session.flush.assert_awaited_once()
    assert session.execute.await_count == 2
