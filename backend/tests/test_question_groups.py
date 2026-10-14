import pytest
from sqlalchemy import event

from app.models import Question
from app.services.question_groups import complete_question_ids, flatten_groups, group_key, ordered_groups


def question(qid, parent="", **kwargs):
    fields = dict(id=qid, qid=f"Q{qid}", bank_group="group", bank="bank", source_file="source.md",
                  parent_stem=parent, stem=f"child {qid}", options=["one", "two"], answer="A", analysis="analysis")
    fields.update(kwargs)
    return Question(**fields)


@pytest.mark.asyncio
async def test_complete_partial_two_three_four_and_explicit_group_order(session):
    session.add_all([question(1), question(2, "two"), question(3, "two"),
                     *[question(i, "three") for i in range(4, 7)],
                     *[question(i, "four") for i in range(7, 11)], question(11)])
    await session.flush()
    assert await ordered_groups(session, [9, 1, 6, 3, 7, 11, 2, 999]) == [
        (7, 8, 9, 10), (1,), (4, 5, 6), (2, 3), (11,)]
    assert await complete_question_ids(session, [9, 1, 6], limit=5) == [7, 8, 9, 10, 1]
    assert await complete_question_ids(session, [1, 9, 6], limit=2) == [1, 7, 8, 9, 10]


@pytest.mark.asyncio
async def test_source_bank_namespace_exact_trim_and_regular_singles(session):
    session.add_all([question(1, " \t\u3000共同病例\r\n"), question(2, "共同病例"),
                     question(3, "共同病例", source_file="other.md"),
                     question(4, "共同病例", bank="other"),
                     question(5, "共同病例", bank_group="other"),
                     question(6, "共同 病例"), question(7, "\t\n"), question(8, ""),
                     question(9, "共同病例", qtype="多选", answer="AB")])
    await session.flush()
    assert await complete_question_ids(session, [2]) == [1, 2, 9]
    assert await complete_question_ids(session, [3, 4, 5, 6, 7, 8]) == [3, 4, 5, 6, 7, 8]
    assert group_key("a", "b", "c", "  ") is None


@pytest.mark.asyncio
async def test_batched_expansion_is_not_capped_at_200_or_500(session):
    session.add_all([question(i) for i in range(1, 502)] + [question(502, "case"), question(503, "case")])
    await session.flush()
    ids = await complete_question_ids(session, [*range(1, 502), 503])
    assert ids == list(range(1, 504))


@pytest.mark.asyncio
async def test_scoped_lookup_does_not_fetch_question_content_or_unrelated_rows(session):
    session.add_all([question(1, "case"), question(2, "case"), question(3, "other")])
    await session.flush()
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert await complete_question_ids(session, [2]) == [1, 2]
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    for statement in statements:
        assert "WHERE" in statement
        assert "questions.stem" not in statement
        assert "questions.options" not in statement
        assert "questions.analysis" not in statement


def test_flatten_empty_zero_and_soft_limit():
    assert flatten_groups([]) == []
    assert flatten_groups([(1, 2)], 0) == []
    assert flatten_groups([(1,), (2, 3, 4), (5,)], 2) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_legacy_embedded_cases_from_either_child_and_namespace(session):
    from app.services.question_groups import legacy_case_parts
    parent = "男，22岁。3天前淋雨后突发寒战、高热、胸痛，咳铁锈色痰。"
    for i in range(1, 5):
        session.add(question(i, stem=f"（18~19题共用题干）{parent}子题{i}？",
                             source_file="a.md" if i <= 2 else "b.md"))
    session.add_all([question(i, stem=f"（1～4题共用题干）{parent}其他子题{i}？") for i in range(5, 9)])
    session.add(question(9, stem="普通单题，无父题。"))
    await session.flush()
    assert await complete_question_ids(session, [2]) == [1, 2]
    assert await complete_question_ids(session, [4, 1, 9]) == [3, 4, 1, 2, 9]
    assert await complete_question_ids(session, [8], limit=1) == [5, 6, 7, 8]
    parts = await legacy_case_parts(session, [2])
    assert parts == {1: (parent, "子题1？", "（18~19题共用题干）"), 2: (parent, "子题2？", "（18~19题共用题干）")}
    assert (await session.get(Question, 2)).parent_stem == ""
    from app.services.quiz import list_questions, question_full
    from app.services.quiz_filters import QuizParams
    result = await list_questions(session, 1, QuizParams(ids=[2]), lite=True)
    assert [q.id for q in result] == [1, 2]
    assert result[0].case_total == 2 and result[1].case_index == 2
    assert result[0].case_group == result[1].case_group
    assert "咳铁锈色痰" in result[0].parent_html
    assert "咳铁锈色痰" not in result[0].stem_html
    assert (await question_full(session, 1, 2)).stem_html == result[1].stem_html


@pytest.mark.asyncio
async def test_legacy_ambiguous_or_incomplete_numbering_is_not_combined(session):
    parent = "患者男性，临床表现详见病例。"
    session.add_all([question(i, stem=f"（1~2题共用题干）{parent}问题{i}？") for i in range(1, 5)])
    session.add(question(5, stem=f"（1~3题共用题干）{parent}问题5？"))
    await session.flush()
    assert await complete_question_ids(session, [1, 5]) == [1, 5]
