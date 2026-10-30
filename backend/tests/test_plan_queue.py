from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import (Card, CardQuestion, PlanSnapshot, PlanTask, PlanTaskSection,
                        QuestionMerge, QuestionRelation, User, UserPlan)
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
async def test_plan_distribution_round_robins_chapters_and_keeps_cases_whole(session):
    session.add(User(id=1, username="learner", password_hash="x"))
    parts = ("甲", "乙", "丙")
    cards = []
    links = []
    questions = []
    for section_index, part in enumerate(parts):
        first = section_index * 6 + 1
        for qid in range(first, first + 6):
            parent = "共同病例" if qid in (7, 8) else ""
            questions.append(question(qid, parent, chapter=part, subject_dir="05-内科学"))
        card_ids = (100 + section_index * 2, 101 + section_index * 2)
        cards.extend(Card(id=cid, subject="内科学", part=part, term=f"{part}-{cid}", body="")
                     for cid in card_ids)
        links.extend(CardQuestion(card_id=card_ids[0], question_id=qid)
                     for qid in range(first, first + 6))
    # Question 1 is shared by two chapter cards, but it remains one scheduled task.
    links.append(CardQuestion(card_id=102, question_id=1))
    session.add_all([*questions, *cards, *links])
    await session.commit()

    await study.set_plan(session, 1, [("内科学", part) for part in parts], 3)
    plan = await session.get(UserPlan, 1)
    tasks = (await session.scalars(select(PlanTask).order_by(PlanTask.position))).all()
    task_links = (await session.scalars(select(PlanTaskSection))).all()
    by_task = {task.id: task for task in tasks}
    section_order = {part: index for index, part in enumerate(parts)}
    primary_part = {}
    for link in task_links:
        task = by_task[link.task_id]
        old = primary_part.get(task.id)
        if old is None or section_order[link.part] < section_order[old]:
            primary_part[task.id] = link.part

    assert plan.total_days == 3
    assert sum(task.kind == "question" for task in tasks) == 18
    assert sum(task.kind == "card" for task in tasks) == 6
    assert len([task for task in tasks if task.kind == "question" and task.target_id == 1]) == 1
    shared = next(task for task in tasks if task.kind == "question" and task.target_id == 1)
    assert {link.part for link in task_links if link.task_id == shared.id} == {"甲", "乙"}

    question_day_counts = {}
    chapter_by_day = {}
    for task in tasks:
        day = (task.due_day - plan.start_day).days + 1
        if task.kind == "question":
            question_day_counts[day] = question_day_counts.get(day, 0) + 1
            counts = chapter_by_day.setdefault(day, {part: 0 for part in parts})
            counts[primary_part[task.id]] += 1
    assert question_day_counts == {1: 6, 2: 6, 3: 6}
    assert all(min(counts.values()) >= 1 and max(counts.values()) - min(counts.values()) <= 2
               for counts in chapter_by_day.values()), chapter_by_day
    assert {part: sum(counts[part] for counts in chapter_by_day.values()) for part in parts} == {
        "甲": 6, "乙": 6, "丙": 6,
    }

    case_days = {task.due_day for task in tasks
                 if task.kind == "question" and task.target_id in (7, 8)}
    assert len(case_days) == 1
    card_day_counts = {}
    for task in tasks:
        if task.kind == "card":
            day = (task.due_day - plan.start_day).days + 1
            card_day_counts[day] = card_day_counts.get(day, 0) + 1
    assert card_day_counts == {1: 2, 2: 2, 3: 2}


@pytest.mark.asyncio
async def test_plan_distribution_weights_chapters_by_remaining_work(session):
    session.add(User(id=1, username="learner", password_hash="x"))
    questions = [question(qid, chapter="大章", subject_dir="05-内科学") for qid in range(1, 10)]
    questions += [question(qid, chapter="小章", subject_dir="05-内科学") for qid in range(10, 13)]
    cards = [Card(id=100, subject="内科学", part="大章", term="大章", body=""),
             Card(id=101, subject="内科学", part="小章", term="小章", body="")]
    links = [CardQuestion(card_id=100, question_id=qid) for qid in range(1, 10)]
    links += [CardQuestion(card_id=101, question_id=qid) for qid in range(10, 13)]
    session.add_all([*questions, *cards, *links])
    await session.commit()

    await study.set_plan(session, 1, [("内科学", "大章"), ("内科学", "小章")], 3)
    plan = await session.get(UserPlan, 1)
    tasks = (await session.scalars(select(PlanTask).where(
        PlanTask.kind == "question",
    ).order_by(PlanTask.position))).all()
    daily = {}
    for task in tasks:
        day = (task.due_day - plan.start_day).days + 1
        daily.setdefault(day, {"大章": 0, "小章": 0})
        daily[day]["大章" if task.target_id <= 9 else "小章"] += 1

    assert daily == {1: {"大章": 3, "小章": 1},
                     2: {"大章": 3, "小章": 1},
                     3: {"大章": 3, "小章": 1}}


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
async def test_practice_dedup_keeps_global_classification_and_explicit_relations_unchanged(session):
    await seed(session)
    # Equivalent exercises share plan work, but never create global identity or relation rows.
    q = question(5, stem="child 1", chapter="一", subject_dir="05-内科学")
    session.add(q)
    await session.flush()
    session.add(CardQuestion(card_id=10, question_id=5))
    await session.commit()
    await configure(session)
    assert 1 in await quiz.plan_day_qids(session, 1, 1)
    assert 5 not in await quiz.plan_day_qids(session, 1, 1)
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
async def test_fresh_identity_uses_canonical_record_when_answers_differ(session):
    session.add_all([question(1, answer="D"), question(2, answer="B")])
    session.add(QuestionMerge(alias_id=2, canonical_id=1, reason="same question; preserve answer discrepancy"))
    await session.flush()

    qs = await quiz.list_questions(session, 1, QuizParams(ids=[2, 1], fresh=True), True)

    assert [q.id for q in qs] == [1]
    assert qs[0].answer == "D"


@pytest.mark.asyncio
async def test_cards_do_not_consume_the_daily_question_quota(session):
    await seed(session)
    session.add_all([Card(id=i, subject="内科学", part="甲", term=f"卡{i}", body="") for i in range(20, 40)])
    await session.commit()
    await configure(session, 4)
    assert await quiz.plan_day_qids(session, 1, 1)
    assert await plan_queue.targets(session, 1, 1, "card")


@pytest.mark.asyncio
async def test_existing_plan_collapses_new_aliases_and_keeps_section_membership(session):
    await seed(session)
    await configure(session, 2)
    before = (await session.scalars(select(PlanTask).where(PlanTask.kind == "question"))).all()
    earliest = min(t.due_day for t in before if t.target_id in (1, 2))
    session.add(QuestionMerge(alias_id=2, canonical_id=1, reason="review after plan creation"))
    await session.commit()
    tasks, links = await plan_queue.read(session, 1)
    questions = [t for t in tasks if t.kind == "question"]
    assert {t.target_id for t in questions} == {1, 3, 4}
    assert len(questions) == 3
    root = next(t for t in questions if t.target_id == 1)
    assert root.due_day == earliest
    assert {(link.subject, link.part) for link in links if link.task_id == root.id} == {
        ("内科学", "甲"), ("内科学", "乙"),
    }
    state = await study.plan_today(session, 1)
    assert state["pending_questions"] == 3
    # A plan link already open on the client may still carry the old alias ID.
    pending = await quiz.list_questions(session, 1, QuizParams(plan_day=1, ids=[2]), True)
    assert [q.id for q in pending] == [1]
    pool = await quiz.pool(session, 1, QuizParams(plan_day=1, ids=[2]), None, 0, 20)
    assert [q.id for q in pool.items] == [1]
    await quiz.attempt(session, 1, 2, [0])
    assert (await study.plan_today(session, 1))["pending_questions"] == 2
    assert 1 not in await quiz.plan_day_qids(session, 1, 1)
    assert 2 not in await quiz.plan_day_qids(session, 1, 1)
    await study.plan_restart(session, 1)
    assert (await study.plan_today(session, 1))["pending_questions"] == 2
    from app.models import Attempt
    assert await session.scalar(select(func.count()).select_from(Attempt)) == 1


@pytest.mark.asyncio
async def test_existing_alias_only_plan_moves_to_final_root_without_losing_other_user_tasks(session):
    await seed(session)
    await study.set_plan(session, 1, [("内科学", "甲")], 1)
    session.add(User(id=2, username="other", password_hash="x"))
    await session.commit()
    await study.set_plan(session, 2, [("内科学", "甲")], 1)
    # The final root is outside the selected section and was never a task.
    session.add(question(5, chapter="外部章节", subject_dir="05-内科学"))
    await session.flush()
    session.add_all([QuestionMerge(alias_id=1, canonical_id=2, reason="first"),
                     QuestionMerge(alias_id=2, canonical_id=5, reason="second")])
    await session.commit()
    assert await quiz.plan_day_qids(session, 1, 1) == [5, 3, 4]
    user2 = (await session.scalars(select(PlanTask).where(
        PlanTask.user_id == 2, PlanTask.kind == "question",
    ))).all()
    assert {t.target_id for t in user2} == {1, 3, 4}
    assert await quiz.plan_day_qids(session, 1, 1) == [5, 3, 4]
