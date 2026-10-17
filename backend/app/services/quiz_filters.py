from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, or_, select

from app.models import Attempt, Question, QuestionProgress

LEVELS = ("bank_group", "bank", "subject_dir", "system", "chapter", "qtype")
SEP = "·"
POOL_FLTS = ("done", "todo", "wrong", "starred", "plan", "mastered")
IDS_MAX = 5000


@dataclass
class QuizParams:
    bank_group: str = ""
    bank: str = ""
    subject_dir: str = ""
    system: str = ""
    chapter: str = ""
    qtype: str = ""
    ids: list[int] | None = None
    plan_day: int | None = None
    starred: bool = False
    wrong: bool = False
    due: bool = False
    random: bool = False
    shuffle: bool = False
    fresh: bool = False
    limit: int | None = None
    extra: dict = field(default_factory=dict)


def parse_ids(raw: str | None) -> list[int] | None:
    if raw is None or not raw.strip():
        return None
    try:
        ids = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "ids 参数格式错误，应为逗号分隔的整数")
    if len(ids) > IDS_MAX:
        raise HTTPException(400, f"ids 最多 {IDS_MAX} 个")
    return ids


def level_condition(level: str, value: str):
    col = getattr(Question, level)
    if level == "bank_group":
        return or_(col == value, col.startswith(value + SEP, autoescape=True))
    if level == "system":
        return col.startswith(value, autoescape=True)
    return col == value


def level_conditions(p: QuizParams, upto: int = len(LEVELS)) -> list:
    return [level_condition(lv, getattr(p, lv)) for lv in LEVELS[:upto] if getattr(p, lv)]


def progress_conditions(p: QuizParams, qp=QuestionProgress) -> list:
    conds = []
    if p.starred:
        conds.append(qp.starred.is_(True))
    if p.wrong:
        conds.append(qp.in_wrongbook.is_(True))
    if p.due:
        conds.append(and_(qp.in_plan.is_(True), qp.due_at.isnot(None), qp.due_at <= datetime.now(timezone.utc)))
    return conds


def answered_condition(uid: int):
    return select(Attempt.id).where(
        Attempt.user_id == uid, Attempt.question_id == Question.id, Attempt.picked != "",
    ).exists()


def pool_flt_condition(flt: str | None, qp=QuestionProgress, *, uid: int):
    if not flt:
        return None
    if flt not in POOL_FLTS:
        raise HTTPException(400, "flt 参数无效，可选：" + "/".join(POOL_FLTS))
    return {
        "done": answered_condition(uid),
        "todo": ~answered_condition(uid),
        "wrong": qp.in_wrongbook.is_(True),
        "starred": qp.starred.is_(True),
        "plan": qp.in_plan.is_(True),
        "mastered": qp.mastered.is_(True),
    }[flt]


def all_conditions(p: QuizParams, plan_ids: list[int] | None = None) -> list:
    conds = level_conditions(p) + progress_conditions(p)
    if p.ids is not None:
        conds.append(Question.id.in_(p.ids))
    if plan_ids is not None:
        conds.append(Question.id.in_(plan_ids))
    return conds
