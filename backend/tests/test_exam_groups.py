import random

import pytest

from app.schemas.quiz import SubmitItem
from app.services import exam
from app.services.question_groups import ordered_groups
from test_question_groups import question


@pytest.mark.parametrize("answer", ["AB", "BC", "A,B", "A、C", "A/B"])
def test_mock_accepts_contiguous_and_separated_multiple_answers(answer):
    assert exam._JUDGEABLE.fullmatch(answer)
    assert exam.type_rank("多选", answer) == 3


@pytest.mark.parametrize("answer", ["", "A或B", "ABC错误", "AJ!"])
def test_mock_excludes_unjudgeable_answers(answer):
    assert not exam._JUDGEABLE.fullmatch(answer)


@pytest.mark.asyncio
async def test_mock_includes_standalone_multiselect_seeds(session):
    session.add_all([
        question(1, answer="AB", qtype="多选"),
        question(2, answer="BC", qtype="多选"),
        question(3, answer="A,B", qtype="多选"),
        question(4, answer="ab", qtype="多选"),
        question(5, answer="不是选项", qtype="多选"),
    ])
    await session.flush()
    assert set(await exam.mock(session, 10)) == {1, 2, 3, 4}
    assert exam.type_rank("多选", "ab") == 3


def assert_adjacent(ids, children):
    if any(i in ids for i in children):
        assert all(i in ids for i in children)
        pos = ids.index(min(children))
        assert ids[pos : pos + len(children)] == sorted(children)


def test_answer_based_types_for_case_children():
    assert exam.type_rank("病例子题", "A") == 1
    assert exam.type_rank("病例子题", "AB") == 3
    assert exam.type_rank("病例串", "B") == 1
    assert exam.type_rank("多选", "BC") == 3


def test_mock_budget_counts_children_and_chooses_fitting_groups():
    pool = [(i, "one", True, 1) for i in range(1, 5)]
    pool.extend((i, "two", True, 3 if i == 7 else 1) for i in range(5, 8))
    pool.extend((i, "two", False, 3 if i == 11 else 1) for i in range(8, 12))
    groups = {i: (5, 6, 7) for i in (5, 6, 7)} | {i: (8, 9, 10, 11) for i in (8, 9, 10, 11)}
    for n in range(1, 12):
        ids = exam.build_mock(pool, n, {"one": 1, "two": 1}, random.Random(6), groups)
        assert len(ids) == n
        assert_adjacent(ids, [5, 6, 7])
        assert_adjacent(ids, [8, 9, 10, 11])
        assert len(ids) == len(set(ids))


def test_impossible_count_overshoots_by_final_group_only():
    pool = [(i, "x", False, 3 if i == 4 else 1) for i in range(1, 5)]
    groups = {i: (1, 2, 3, 4) for i in range(1, 5)}
    assert exam.build_mock(pool, 2, rng=random.Random(1), groups=groups) == [1, 2, 3, 4]
    assert exam.build_mock(pool, 12, rng=random.Random(1), groups=groups) == [1, 2, 3, 4]
    with pytest.raises(ValueError, match="every case child"):
        exam.build_mock(pool[:1], 2, groups=groups)


@pytest.mark.asyncio
async def test_mock_completes_partial_eligible_seeds_including_invalid_answer_and_qtype(session):
    session.add_all([question(1, "case", qtype="病例子题", answer="A", system="a"),
                     question(2, "case", qtype="病例子题", answer="AB", system="a"),
                     question(3, "case", qtype="other", answer="", system="a"),
                     question(4, "case", qtype="病例子题", answer="B?", system="a"),
                     question(5, "case", qtype="病例子题", answer="C", system="a", bank="other"),
                     question(6, "", qtype="单选", answer="A", system="a")])
    await session.flush()
    assert await ordered_groups(session, [1]) == [(1, 2, 3, 4)]
    ids = await exam.mock(session, 10)
    assert set(ids) == {1, 2, 3, 4, 5, 6}
    assert_adjacent(ids, [1, 2, 3, 4])
    assert ids.index(5) not in range(ids.index(1), ids.index(1) + 4)


@pytest.mark.asyncio
async def test_mock_many_cases_2_3_4_children_and_singles(session):
    session.add_all([question(1, "two", answer="A"), question(2, "two", answer="AB"),
                     question(3, "three", answer="A"), question(4, "three", answer="A"), question(5, "three", answer="AB"),
                     *[question(i, "four", answer="AB" if i == 9 else "A") for i in range(6, 10)],
                     *[question(i) for i in range(10, 15)]])
    await session.flush()
    ids = await exam.mock(session, 10)
    assert 10 <= len(ids) <= 13
    for case in [(1, 2), (3, 4, 5), (6, 7, 8, 9)]:
        assert_adjacent(ids, case)
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_submit_accepts_expanded_case_over_old_500_child_limit(session):
    session.add_all([question(i) for i in range(1, 500)] + [
        question(i, "final case") for i in range(500, 504)
    ])
    await session.flush()
    items = [SubmitItem(question_id=i, picked=[]) for i in range(1, 504)]
    report = await exam.submit(session, 1, "", items)
    assert len(report.results) == 503
    assert report.total == 0
