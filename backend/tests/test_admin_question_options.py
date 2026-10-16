import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Question, QuestionEdit, User
from app.schemas.admin import AdminQuestionPatch
from app.services import quiz


async def seed_question(session):
    session.add(User(id=7, username="editor", password_hash="x", is_admin=True))
    session.add(Question(
        id=91, qid="ADMIN-91", subject_dir="病理学", system="循环系统疾病",
        stem="原题干", options=["左心室扩大", "二尖瓣狭窄", "心包积液", "纤维性心包炎"],
        answer="C", analysis="原解析",
    ))
    await session.commit()


@pytest.mark.asyncio
async def test_admin_can_read_and_update_options_and_answer(session):
    await seed_question(session)
    before = await quiz.get_question(session, 91)
    assert before.options[2] == "心包积液"
    assert before.answer == "C"

    changed = await quiz.update_question(session, 7, 91, AdminQuestionPatch(
        options=["左心室扩大", "二尖瓣狭窄", "心包积液（增多）", "纤维性心包炎"],
        answer="ac",
    ))
    assert changed == 2
    stored = await session.get(Question, 91)
    assert stored.options[2] == "心包积液（增多）"
    assert stored.answer == "AC"
    edits = (await session.execute(select(QuestionEdit.field).where(QuestionEdit.question_id == 91))).scalars().all()
    assert edits == ["options", "answer"]


@pytest.mark.asyncio
async def test_admin_option_update_rejects_invalid_answer(session):
    await seed_question(session)
    with pytest.raises(HTTPException, match="同时填写有效的正确答案"):
        await quiz.update_question(session, 7, 91, AdminQuestionPatch(options=["甲", "乙"]))
    with pytest.raises(HTTPException, match="超出当前选项范围"):
        await quiz.update_question(session, 7, 91, AdminQuestionPatch(answer="E"))
