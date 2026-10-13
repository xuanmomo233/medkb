from datetime import datetime, timedelta, timezone

import pytest

from app.models import Attempt, QuestionProgress as QP
from app.services import quiz
from app.services.quiz_filters import QuizParams
from test_question_groups import question

CASES = [{2, 7, 9}, {3, 4}, {5, 10, 12, 13}]


async def populate(session):
    session.add_all([question(1), *[question(i, "three") for i in [2, 7, 9]],
                     *[question(i, "two") for i in [3, 4]],
                     *[question(i, "four") for i in [5, 10, 12, 13]],
                     question(6), question(8), question(11)])
    await session.flush()


def assert_atomic(ids):
    for case in CASES:
        if case.intersection(ids):
            assert case.issubset(ids)
            start = min(ids.index(i) for i in case)
            assert ids[start : start + len(case)] == sorted(case)
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_regular_limit_finishes_case_and_keeps_singles(session):
    await populate(session)
    out = await quiz.list_questions(session, 1, QuizParams(), False)
    assert [q.id for q in out] == [1, 2, 7, 9, 3, 4, 5, 10, 12, 13, 6, 8, 11]
    out = await quiz.list_questions(session, 1, QuizParams(limit=2), False)
    assert [q.id for q in out] == [1, 2, 7, 9]
    assert out[0].case_group == "" and out[0].case_total == 0
    assert [q.case_index for q in out[1:]] == [1, 2, 3]
    assert {q.case_total for q in out[1:]} == {3}
    assert len({q.case_group for q in out[1:]}) == 1
    assert await quiz.list_questions(session, 1, QuizParams(ids=[]), True) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [{}, {"shuffle": True}, {"random": True}])
async def test_explicit_partial_ids_keep_requested_group_order_even_with_flags(session, flags):
    await populate(session)
    out = await quiz.list_questions(session, 1, QuizParams(ids=[13, 1, 9, 4, 7, 999], limit=1, **flags), True)
    assert [q.id for q in out] == [5, 10, 12, 13, 1, 2, 7, 9, 3, 4]


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["wrong", "starred", "due"])
async def test_progress_filters_select_seed_not_sibling_progress(session, flag):
    await populate(session)
    now = datetime.now(timezone.utc)
    session.add_all([QP(user_id=1, question_id=7, in_wrongbook=True, starred=True, in_plan=True,
                        due_at=now - timedelta(days=1), last_seen_at=now),
                     QP(user_id=1, question_id=2, mastered=True),
                     QP(user_id=2, question_id=4, in_wrongbook=True, starred=True)])
    await session.flush()
    out = await quiz.list_questions(session, 1, QuizParams(**{flag: True}), True)
    assert [q.id for q in out] == [2, 7, 9]
    assert out[0].state == "mastered"
    assert out[1].starred and out[1].done
    assert not out[2].starred and not out[2].done


@pytest.mark.asyncio
@pytest.mark.parametrize("flt", ["wrong", "starred", "mastered"])
async def test_pool_filtered_partial_selection_expands_in_practice_or_test(session, flt):
    await populate(session)
    session.add(QP(user_id=1, question_id=7, in_wrongbook=True, starred=True, mastered=True))
    await session.flush()
    page = await quiz.pool(session, 1, QuizParams(), flt, 0, 50)
    assert [it.id for it in page.items] == [7]
    out = await quiz.list_questions(session, 1, QuizParams(ids=[it.id for it in page.items]), True)
    assert [q.id for q in out] == [2, 7, 9]


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["random", "shuffle"])
async def test_randomized_selection_always_adjacent_and_soft_limited(session, flag):
    await populate(session)
    session.add(QP(user_id=1, question_id=7, mastered=True))
    await session.flush()
    for _ in range(12):
        out = await quiz.list_questions(session, 1, QuizParams(limit=4, **{flag: True}), True)
        ids = [q.id for q in out]
        assert 4 <= len(ids) <= 7
        assert_atomic(ids)
    # Only the unmastered sibling may be a random seed, but the mastered child
    # is still required once the case is selected.
    out = await quiz.list_questions(session, 1, QuizParams(random=True, ids=None, qtype="单选", limit=120), True)
    assert 7 in [q.id for q in out]


@pytest.mark.asyncio
async def test_plan_and_qtype_seeds_do_not_hide_siblings(session, monkeypatch):
    session.add_all([question(1, "case", qtype="单选"), question(2, "case", qtype="多选", answer="AB")])
    await session.flush()
    out = await quiz.list_questions(session, 1, QuizParams(qtype="单选"), True)
    assert [q.id for q in out] == [1, 2]
    async def plan_ids(*args):
        return [2]
    monkeypatch.setattr(quiz, "plan_day_qids", plan_ids)
    out = await quiz.list_questions(session, 1, QuizParams(plan_day=1), True)
    assert [q.id for q in out] == [1, 2]


@pytest.mark.asyncio
async def test_lite_full_response_fields_and_sibling_attempts(session):
    session.add_all([question(1, "病例", analysis="**解析**"), question(2, "病例", analysis="")])
    session.add_all([Attempt(id=1, user_id=1, question_id=1, picked="A", is_correct=True),
                     Attempt(id=2, user_id=1, question_id=1, picked="B", is_correct=False),
                     Attempt(id=3, user_id=2, question_id=1, picked="A", is_correct=True)])
    await session.flush()
    lite = await quiz.list_questions(session, 1, QuizParams(ids=[2]), True)
    full = await quiz.list_questions(session, 1, QuizParams(ids=[2]), False)
    assert [q.id for q in lite] == [1, 2] == [q.id for q in full]
    assert lite[0].last_picked == "B" and lite[0].last_correct is False
    assert lite[1].last_picked == "" and lite[1].last_correct is None
    assert all(q.analysis_html == "" for q in lite)
    assert full[0].analysis_html and not full[0].analysis_empty
    assert full[1].analysis_html == "" and full[1].analysis_empty
    assert lite[0].parent_html == full[0].parent_html == lite[1].parent_html
    assert lite[0].model_dump().keys() == full[0].model_dump().keys()
    detail = await quiz.question_full(session, 1, 1)
    assert detail.analysis_html == full[0].analysis_html
    assert detail.stat.total == 3
