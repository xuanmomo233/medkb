from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin


class QuestionProgress(Base):
    """用户-题目进度。错题本/掌握/复习计划是三个独立标记（API 的 state 由它们派生：mastered > again > plan）。"""

    __tablename__ = "question_progress"
    __table_args__ = (Index("ix_qp_user_flags", "user_id", "in_wrongbook", "mastered"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    in_wrongbook: Mapped[bool] = mapped_column(Boolean, default=False)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    in_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class CardProgress(Base):
    __tablename__ = "card_progress"
    __table_args__ = (Index("ix_cp_user_flags", "user_id", "in_wrongbook", "mastered"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
    in_wrongbook: Mapped[bool] = mapped_column(Boolean, default=False)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    in_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Exam(Base, CreatedMixin):
    """测试/模考交卷记录。"""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(80), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)


class Attempt(Base, CreatedMixin):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_user_q", "user_id", "question_id"),
        Index("ix_attempts_user_time", "user_id", "created_at"),
        Index("ix_attempts_q_correct", "question_id", "is_correct"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    exam_id: Mapped[int | None] = mapped_column(ForeignKey("exams.id", ondelete="SET NULL"))
    picked: Mapped[str] = mapped_column(String(26), default="")
    is_correct: Mapped[bool] = mapped_column(Boolean)


class ScheduleItem(Base, CreatedMixin):
    """系统生成的每日日程条目（薄弱点补强/到期复习）。"""

    __tablename__ = "schedule_items"
    __table_args__ = (Index("ix_sched_user_day", "user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    item_type: Mapped[str] = mapped_column(String(8))  # question | card
    item_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(16))  # due | weak
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
