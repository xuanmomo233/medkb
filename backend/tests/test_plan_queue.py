from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import (Card, CardQuestion, PlanSnapshot, PlanTask, PlanTaskSection,
                        QuestionMerge, QuestionRelation, User)
from app.services import plan_queue, progress, question_links, quiz, study
from app.services.exam import submit
from app.services.quiz_filters import QuizParams
from test_question_groups import question


async def seed(session):
    session.add(User(id=1, username="learner", password_hash="x"))
    session.add_all([question(1, chapter="一", subject_dir="05-内科学"),
                     question(2, chapter="二", subject_dir="05-内科学"),
                     question(3, "共同病例", chapter="一", subject_dir="05-内科学"),
                     question(4, "共同病例", chapter="一", subject_dir="05-内科学")])
    session.add_all([Card(id=10, subject="内科学", part="甲", term="甲", body=""),
                     Card(id=11, subject="内科学", part="乙", term="乙", body="")])
    await session.flush()
    session.add_all([CardQuestion(card_id=10, question_id=1), CardQuestion(card_id=11, question_id=1),
                     CardQuestion(card_id=11, question_id=2), CardQuestion(card_id=10, question_id=3)])
    await session.commit()


async def configure(session, days=1):
    await study.set_plan(session, 1, [("内科学", "甲"), ("内科学", "乙")], days)


@pytest.mark.asyncio
async def test_shared_question_is_one_task_and_satisfies_both_sections(session):
    await seed(session)
    await configure(session)
    ids = await quiz.plan_day_qids(session, 1, 1)
    assert set(ids) == {1, 2, 3, 4} and len(ids) == 4
    tasks = (await session.scalars(select(PlanTask).where(PlanTask.kind == "question"))).all()
    assert len(tasks) == 4
    shared = next(task for task in tasks if task.target_id == 1)
    assert len((await session.scalars(select(PlanTaskSection).where(PlanTaskSection.task_id == shared.id))).all()) == 2
    result = await quiz.attempt(session, 1, 1, [1])
    assert result.correct is False  # A wrong answer completes first-pass work, not mastery.
    p = await study.plan_today(session, 1)
    assert p["today_questions"] == 3
    assert all(it["question_done"] == 1 for it in p["items"])
    for _ in range(2):
        assert await quiz.plan_day_qids(session, 1, 1) == [3, 4, 2]


@pytest.mark.asyncio
async def test_prior_attempts_and_outside_practice_survive_edit_and_restart(session):
    await seed(session)
    await quiz.attempt(session, 1, 1, [0])
    await configure(session)
    assert 1 not in await quiz.plan_day_qids(session, 1, 1)
    await quiz.attempt(session, 1, 2, [0])  # Normal practice, without a plan parameter.
    assert (await study.plan_today(session, 1))["pending_questions"] == 2
    await study.plan_restart(session, 1)
    await configure(session, 3)
    tasks = (await session.scalars(select(PlanTask).where(PlanTask.kind == "question"))).all()
    assert {task.target_id for task in tasks if task.completed_at} == {1, 2}
    assert (await study.plan_today(session, 1))["pending_questions"] == 2


@pytest.mark.asyncio
async def test_case_context_preserved_without_reissuing_completed_child(session):
    await seed(session)
    await configure(session)
    await quiz.attempt(session, 1, 3, [0])
    qs = await quiz.list_questions(session, 1, QuizParams(plan_day=1), True)
    assert 3 not in [q.id for q in qs]
    child = next(q for q in qs if q.id == 4)
    assert "共同病例" in child.parent_html
    assert len(qs) == 3
    # Explicit links from plan detail are intersected with pending work too.
    qs = await quiz.list_questions(session, 1, QuizParams(plan_day=1, ids=[3, 4]), True)
    assert [q.id for q in qs] == [4]


@pytest.mark.asyncio
async def test_daily_tasks_frozen_and_deadline_is_not_completion(session, monkeypatch):
    await seed(session)
    await configure(session, 2)
    first = await quiz.plan_day_qids(session, 1, 1)
    second = await quiz.plan_day_qids(session, 1, 2)
    assert first and second and not set(first).intersection(second)
    tasks_before = {t.id: t.due_day for t in (await session.scalars(select(PlanTask))).all()}
    for qid in first:
        await quiz.attempt(session, 1, qid, [0])
    assert await quiz.plan_day_qids(session, 1, 1) == []
    assert await quiz.plan_day_qids(session, 1, 2) == second
    assert {t.id: t.due_day for t in (await session.scalars(select(PlanTask))).all()} == tasks_before
    today = study.local_today()
    monkeypatch.setattr(study, "local_today", lambda: today + timedelta(days=3))
    p = await study.plan_today(session, 1)
    assert not p["finished"]
    assert await quiz.plan_day_qids(session, 1, 1) == second


@pytest.mark.asyncio
async def test_submission_cards_and_empty_selection_sync_without_false_seen(session):
    await seed(session)
    await configure(session)
    await progress.mark(session, 1, "question", 1, "plan")
    assert 1 in await quiz.plan_day_qids(session, 1, 1)
    from app.schemas.quiz import SubmitItem
    await submit(session, 1, "练习", [SubmitItem(question_id=1, picked=[0]), SubmitItem(question_id=2, picked=[])])
    assert 1 not in await quiz.plan_day_qids(session, 1, 1)
    assert 2 in await quiz.plan_day_qids(session, 1, 1)
    for qid in (2, 3, 4):
        await quiz.attempt(session, 1, qid, [0])
    for cid in (10, 11):
        await progress.mark(session, 1, "card", cid, "seen")
    assert (await study.plan_today(session, 1))["finished"]
    assert await plan_queue.targets(session, 1, 1, "card") == []
    detail = await study.plan_day_detail(session, 1, 1)
    assert detail["cards"] == [] and detail["question_groups"] == []
    await study.clear_plan(session, 1)
    for model in (PlanSnapshot, PlanTask, PlanTaskSection):
        assert await session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.asyncio
async def test_no_automatic_classification_and_only_explicit_related_questions(session):
    await seed(session)
    # Two identical bodies intentionally remain independent until classification is authorized.
    q = question(5, stem="child 1", chapter="一", subject_dir="05-内科学")
    session.add(q)
    await session.flush()
    session.add(CardQuestion(card_id=10, question_id=5))
    await session.commit()
    await configure(session)
    plan_ids = set(await quiz.plan_day_qids(session, 1, 1))
    # Exact-display practice dedup may share work without creating identity links.
    assert 1 in plan_ids and 5 not in plan_ids
    assert await question_links.related(session, 1, 1) == []
    assert await session.scalar(select(func.count()).select_from(QuestionMerge)) == 0
    assert await session.scalar(select(func.count()).select_from(QuestionRelation)) == 0
    # Synthetic explicit relations exercise the architecture, not production classification.
    session.add(QuestionRelation(left_id=1, right_id=2, kind="variant", reason="改变判断条件"))
    await session.commit()
    out = await question_links.related(session, 1, 1)
    assert [r["id"] for r in out] == [2]
    assert out[0]["in_plan"] and out[0]["reason"] == "改变判断条件"
    assert "answer" not in out[0] and "analysis" not in out[0]
    await quiz.attempt(session, 1, 2, [0])
    assert await question_links.related(session, 1, 1) == []


@pytest.mark.asyncio
async def test_empty_snapshot_is_not_rebuilt_and_users_are_isolated(session):
    await seed(session)
    session.add(User(id=2, username="other", password_hash="x"))
    await session.commit()
    await study.set_plan(session, 1, [("内科学", "空章节")], 1)
    assert (await study.plan_today(session, 1))["finished"]
    assert await session.get(PlanSnapshot, 1) is not None
    await configure(session)
    await quiz.attempt(session, 2, 1, [0])
    assert 1 in await quiz.plan_day_qids(session, 1, 1)
    assert await quiz.plan_day_qids(session, 2, 1) == []


@pytest.mark.asyncio
async def test_plan_cards_resume_only_pending_and_shared_read_models_agree(session):
    from app.services.cards import list_cards

    await seed(session)
    await configure(session)
    params = dict(subject=None, part=None, ids=None, plan_day=1, starred=False, due=False)
    assert [c["id"] for c in await list_cards(session, 1, **params)] == [10, 11]
    await progress.mark(session, 1, "card", 10, "seen")
    assert [c["id"] for c in await list_cards(session, 1, **params)] == [11]
    state = await study.plan_today(session, 1)
    detail = await study.plan_day_detail(session, 1, 1)
    assert state["today_cards"] == len(detail["cards"]) == 1
    assert [c["id"] for c in detail["cards"]] == [11]


@pytest.mark.asyncio
async def test_fresh_related_practice_never_expands_a_done_case_child(session):
    await seed(session)
    await quiz.attempt(session, 1, 3, [0])
    qs = await quiz.list_questions(session, 1, QuizParams(ids=[4], fresh=True), True)
    assert [q.id for q in qs] == [4]
    assert qs[0].parent_html


@pytest.mark.asyncio
async def test_cards_do_not_consume_the_daily_question_quota(session):
    await seed(session)
    session.add_all([Card(id=i, subject="内科学", part="甲", term=f"卡{i}", body="") for i in range(20, 40)])
    await session.commit()
    await configure(session, 4)
    assert await quiz.plan_day_qids(session, 1, 1)
    assert await plan_queue.targets(session, 1, 1, "card")
