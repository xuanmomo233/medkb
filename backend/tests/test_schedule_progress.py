from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Attempt, QuestionProgress, ScheduleDay, ScheduleItem
from app.schemas.quiz import SubmitItem
from app.services import exam, progress, quiz, study
from test_plan_queue import seed


async def schedule(session):
    await seed(session)
    session.add_all([
        ScheduleItem(id=101, user_id=1, day=study.local_today(), item_type="question", item_id=1, reason="due"),
        ScheduleItem(id=102, user_id=1, day=study.local_today(), item_type="card", item_id=10, reason="due"),
        ScheduleItem(id=103, user_id=1, day=study.local_today(), item_type="question", item_id=2, reason="weak"),
    ])
    await session.commit()


@pytest.mark.asyncio
async def test_attempt_completes_schedule_from_any_entry_and_advances_review_once(session):
    await schedule(session)
    assert (await study.schedule_today(session, 1))["done_count"] == 0
    await quiz.attempt(session, 1, 1, [0])
    day = await study.schedule_today(session, 1)
    assert day["done_count"] == 1 and day["items"][0]["done"]
    qp = await session.get(QuestionProgress, (1, 1))
    assert qp.reps == 1 and qp.interval_days == 1 and qp.due_at is not None
    await quiz.attempt(session, 1, 1, [0])
    assert qp.reps == 1  # A temporary re-practice is not a second scheduled review.
    assert (await study.schedule_today(session, 1))["done_count"] == 1


@pytest.mark.asyncio
async def test_card_needs_real_study_and_exam_needs_a_valid_answer(session):
    await schedule(session)
    await progress.mark(session, 1, "card", 10, "star")
    assert (await study.schedule_today(session, 1))["done_count"] == 0
    await progress.mark(session, 1, "card", 10, "rate_again")
    assert (await study.schedule_today(session, 1))["done_count"] == 1
    await exam.submit(session, 1, "日程", [SubmitItem(question_id=2, picked=[])])
    assert (await study.schedule_today(session, 1))["done_count"] == 1
    await exam.submit(session, 1, "日程", [SubmitItem(question_id=2, picked=[1])])
    assert (await study.schedule_today(session, 1))["done_count"] == 2


@pytest.mark.asyncio
async def test_today_reconciles_legacy_attempts_but_not_yesterdays(session):
    await schedule(session)
    session.add(Attempt(user_id=1, question_id=1, picked="A", is_correct=True,
                        created_at=study.day_start_utc(study.local_today()) - timedelta(hours=1)))
    session.add(Attempt(user_id=1, question_id=2, picked="B", is_correct=False,
                        created_at=study.utcnow()))
    await session.commit()
    day = await study.schedule_today(session, 1)
    assert [item["item_id"] for item in day["items"] if item["done"]] == [2]


@pytest.mark.asyncio
async def test_empty_day_is_frozen_and_does_not_regenerate_after_every_visit(session):
    await seed(session)
    assert (await study.schedule_today(session, 1))["items"] == []
    assert await session.get(ScheduleDay, (1, study.local_today())) is not None
    session.add(QuestionProgress(user_id=1, question_id=1, in_plan=True,
                                 due_at=study.utcnow() - timedelta(days=1)))
    await session.commit()
    assert (await study.schedule_today(session, 1))["items"] == []


@pytest.mark.asyncio
async def test_generation_excludes_questions_already_answered_today(session):
    await seed(session)
    await quiz.attempt(session, 1, 1, [0])
    qp = await session.get(QuestionProgress, (1, 1))
    qp.in_plan, qp.due_at = True, study.utcnow() - timedelta(days=1)
    session.add(QuestionProgress(user_id=1, question_id=2, in_plan=True,
                                 due_at=study.utcnow() - timedelta(days=1)))
    await session.commit()
    day = await study.schedule_today(session, 1)
    assert [item["item_id"] for item in day["items"] if item["item_type"] == "question"] == [2]


@pytest.mark.asyncio
async def test_other_users_and_old_schedules_are_not_completed(session):
    await schedule(session)
    session.add(ScheduleItem(user_id=1, day=study.local_today() - timedelta(days=1),
                             item_type="question", item_id=1, reason="due"))
    await session.commit()
    await quiz.attempt(session, 1, 1, [0])
    old = await session.scalar(select(ScheduleItem).where(ScheduleItem.day < study.local_today()))
    assert old.done_at is None
