"""Persisted plan assignments and explicitly reviewed question relationships."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin


class QuestionMerge(Base, CreatedMixin):
    __tablename__ = "question_merges"
    __table_args__ = (CheckConstraint("alias_id <> canonical_id", name="ck_question_merge_distinct"),)

    alias_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True)
    canonical_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")


class QuestionRelation(Base, CreatedMixin):
    __tablename__ = "question_relations"
    __table_args__ = (
        UniqueConstraint("left_id", "right_id", "kind", name="uq_question_relation"),
        CheckConstraint("left_id < right_id", name="ck_question_relation_order"),
        CheckConstraint("kind IN ('variant', 'same_concept', 'contrast')", name="ck_question_relation_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    left_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    right_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text, default="")


class PlanSnapshot(Base, CreatedMixin):
    """An empty snapshot is valid; it must not be regenerated on every read."""

    __tablename__ = "plan_snapshots"
    user_id: Mapped[int] = mapped_column(ForeignKey("user_plans.user_id", ondelete="CASCADE"), primary_key=True)


class ScheduleDay(Base, CreatedMixin):
    __tablename__ = "schedule_days"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)


class PlanTask(Base):
    __tablename__ = "plan_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "target_id", name="uq_plan_task_target"),
        CheckConstraint("kind IN ('question', 'card')", name="ck_plan_task_kind"),
        Index("ix_plan_tasks_pending", "user_id", "kind", "due_day", "completed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_plans.user_id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int] = mapped_column()
    position: Mapped[int] = mapped_column()
    due_day: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanTaskSection(Base):
    __tablename__ = "plan_task_sections"

    task_id: Mapped[int] = mapped_column(ForeignKey("plan_tasks.id", ondelete="CASCADE"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), primary_key=True)
    part: Mapped[str] = mapped_column(String(64), primary_key=True)
