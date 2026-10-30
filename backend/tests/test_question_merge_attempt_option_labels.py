import pytest
from sqlalchemy import select

from app.models import Attempt, QuestionMerge, User
from app.services import quiz
from app.services.quiz_filters import QuizParams
from test_question_groups import question


@pytest.mark.asyncio
async def test_option_reordering_keeps_merged_history_semantic(session):
    canonical = question(
        1,
        stem="骨盆骨折早期最危险的并发症是",
        qtype="单选",
        options=["出血性休克", "膀胱、尿道破裂", "坐骨神经损伤", "直肠损伤"],
        answer="A",
    )
    alias = question(
        2,
        stem="2015N90A 骨盆骨折早期最危险的并发症是",
        qtype="单选",
        options=["膀胱、尿道破裂", "坐骨神经损伤", "直肠损伤", "出血性休克"],
        answer="D",
    )
    session.add_all([
        User(id=7, username="merge-history", password_hash="x", is_admin=False),
        canonical,
        alias,
        QuestionMerge(alias_id=2, canonical_id=1, reason="same question; options reordered"),
        Attempt(id=1, user_id=7, question_id=1, picked="A", is_correct=True),
        Attempt(id=2, user_id=7, question_id=2, picked="D", is_correct=True),
    ])
    await session.flush()

    stat = await quiz.question_stat(session, 1)
    assert stat.total == 2 and stat.correct == 2
    assert stat.dist == {"A": 2}

    listed = await quiz.list_questions(session, 7, QuizParams(ids=[2]), lite=True)
    assert [item.id for item in listed] == [1]
    assert listed[0].last_picked == "A"
    assert listed[0].last_correct is True

    attempts = (await session.scalars(select(Attempt).order_by(Attempt.id))).all()
    assert [(item.question_id, item.picked) for item in attempts] == [(1, "A"), (2, "D")]


def test_option_label_translation_uses_source_labels_when_noncontiguous():
    canonical_options = ["出血性休克", "膀胱、尿道破裂", "坐骨神经损伤", "直肠损伤"]
    alias_options = ["膀胱、尿道破裂", "坐骨神经损伤", "直肠损伤", "出血性休克"]
    assert quiz.remap_picked_to_target(
        "E", alias_options, ["A", "C", "D", "E"], canonical_options, ["A", "B", "C", "D"],
    ) == "A"


def test_option_label_translation_does_not_guess_for_alias_only_distractor():
    canonical_options = ["出血性休克", "膀胱、尿道破裂"]
    alias_options = ["来源特有干扰项", "出血性休克", "膀胱、尿道破裂"]
    assert quiz.remap_picked_to_target("A", alias_options, [], canonical_options, []) is None


@pytest.mark.parametrize("mode", ["practice", "exam"])
@pytest.mark.parametrize("picked,correct,letter", [([1], True, "A"), ([0], False, "K")])
async def test_cached_alias_submission_uses_source_positions(session, mode, picked, correct, letter):
    from app.schemas.quiz import SubmitItem
    from app.services import exam

    session.add_all([
        User(id=7, username="cached-alias", password_hash="x"),
        question(1, options=["正确内容", "错误内容"], option_labels=["A", "K"], answer="A"),
        question(2, options=["错误内容", "正确内容"], option_labels=["J", "Z"], answer="Z"),
        QuestionMerge(alias_id=2, canonical_id=1, reason="fixture"),
        Attempt(id=99, user_id=7, question_id=2, picked="Z", is_correct=True),
    ])
    await session.commit()
    if mode == "practice":
        result = await quiz.attempt(session, 7, 2, picked)
        assert result.correct is correct
    else:
        result = await exam.submit(session, 7, "合成模考", [SubmitItem(question_id=2, picked=picked)])
        assert result.total == 1 and result.correct == int(correct)
    attempts = (await session.scalars(select(Attempt).order_by(Attempt.id))).all()
    assert [(a.question_id, a.picked, a.is_correct) for a in attempts] == [
        (2, "Z", True), (1, letter, correct),
    ]


@pytest.mark.parametrize("mode", ["practice", "exam"])
@pytest.mark.parametrize("target_options", [["其他内容", "又一内容"], ["重复内容", "重复内容"]])
async def test_unmappable_alias_submission_rejects_before_recording(session, mode, target_options):
    from fastapi import HTTPException
    from sqlalchemy import func
    from app.models import Exam, QuestionProgress
    from app.schemas.quiz import SubmitItem
    from app.services import exam

    session.add_all([
        User(id=7, username="ambiguous-alias", password_hash="x"),
        question(1, options=target_options, answer="A"),
        question(2, options=["重复内容", "来源内容"], answer="A"),
        QuestionMerge(alias_id=2, canonical_id=1, reason="fixture"),
    ])
    await session.commit()
    with pytest.raises(HTTPException) as error:
        if mode == "practice":
            await quiz.attempt(session, 7, 2, [0])
        else:
            await exam.submit(session, 7, "拒绝用例", [SubmitItem(question_id=2, picked=[0])])
    assert error.value.status_code == 409
    for model in [Attempt, Exam, QuestionProgress]:
        assert await session.scalar(select(func.count()).select_from(model)) == 0
