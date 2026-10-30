from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import PlanTask
from app.services import plan_queue


@pytest.mark.asyncio
async def test_canonicalization_visits_section_links_linearly(monkeypatch):
    """A large existing plan must not scan every link for every question."""
    count = 2000
    visits = 0

    class Link:
        subject = "subject"
        part = "part"

        def __init__(self, task_id):
            self._task_id = task_id

        @property
        def task_id(self):
            nonlocal visits
            visits += 1
            return self._task_id

    tasks = [PlanTask(id=i, user_id=1, kind="question", target_id=i,
                      position=i, due_day=date(2026, 10, 18)) for i in range(1, count + 1)]
    links = [Link(task.id) for task in tasks]
    monkeypatch.setattr(plan_queue.question_links, "redirects", AsyncMock(return_value={}))
    result_tasks, result_links = await plan_queue._canonicalize_questions(SimpleNamespace(), tasks, links)

    assert result_tasks == tasks
    assert result_links == links
    assert visits <= count * 4
