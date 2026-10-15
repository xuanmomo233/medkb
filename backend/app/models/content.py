from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, JsonType


class Chapter(Base):
    """章节正文/思维导图（旧 chapters 表）。kind: mindmap | note"""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    subject: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content_md: Mapped[str] = mapped_column(Text, default="")
    source_file: Mapped[str] = mapped_column(String(255), default="")
    pages: Mapped[list] = mapped_column(JsonType, default=list)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_filter", "bank_group", "bank", "subject_dir", "system"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    qid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    bank_group: Mapped[str] = mapped_column(String(64), default="", index=True)
    bank: Mapped[str] = mapped_column(String(64), default="", index=True)
    subject_dir: Mapped[str] = mapped_column(String(32), default="", index=True)
    system: Mapped[str] = mapped_column(String(64), default="", index=True)
    chapter: Mapped[str] = mapped_column(String(200), default="", index=True)
    qtype: Mapped[str] = mapped_column(String(16), default="单选", index=True)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JsonType, default=list)
    answer: Mapped[str] = mapped_column(String(255), default="")
    analysis: Mapped[str] = mapped_column(Text, default="")
    parent_stem: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[str] = mapped_column(Text, default="")
    source_file: Mapped[str] = mapped_column(String(255), default="")
    tags: Mapped[list] = mapped_column(JsonType, default=list)
    is_real_exam: Mapped[bool] = mapped_column(default=False, index=True)


class Card(Base):
    """背卡（旧 kp_items_v2）。"""

    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_subject_part", "subject", "part"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(32))
    part: Mapped[str] = mapped_column(String(64))
    section: Mapped[str] = mapped_column(String(128), default="")
    term: Mapped[str] = mapped_column(String(200), index=True)
    hint: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(String(255), default="")


class TextbookSource(Base, CreatedMixin):
    """可引用的教材版本；书目与内容定位分开，避免每条出处重复填写版次。"""

    __tablename__ = "textbook_sources"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(32), index=True)
    publisher: Mapped[str] = mapped_column(String(100), default="人民卫生出版社")
    edition: Mapped[str] = mapped_column(String(32), default="第十版")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ContentCitation(Base, CreatedMixin):
    """章节、题目或背卡到教材具体位置的核验记录。"""

    __tablename__ = "content_citations"
    __table_args__ = (
        CheckConstraint("target_type IN ('chapter', 'question', 'card')", name="ck_citation_target_type"),
        CheckConstraint("status IN ('unverified', 'verified', 'disputed')", name="ck_citation_status"),
        CheckConstraint("page_start IS NULL OR page_start > 0", name="ck_citation_page_start"),
        CheckConstraint("page_end IS NULL OR page_end > 0", name="ck_citation_page_end"),
        CheckConstraint("page_end IS NULL OR page_start IS NOT NULL", name="ck_citation_page_pair"),
        CheckConstraint("page_end IS NULL OR page_end >= page_start", name="ck_citation_page_order"),
        UniqueConstraint(
            "target_type", "target_id", "source_key", "chapter", "section", "page_start", "page_end",
            name="uq_content_citation_location",
        ),
        Index("ix_content_citation_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[int] = mapped_column(Integer)
    source_key: Mapped[str] = mapped_column(ForeignKey("textbook_sources.key", ondelete="RESTRICT"), index=True)
    chapter: Mapped[str] = mapped_column(String(200), default="")
    section: Mapped[str] = mapped_column(String(200), default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="unverified", index=True)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CardQuestion(Base):
    """卡片与源题的多对多关联，替代旧版 qids 文本字段（'[Q123] [Q456]'）。"""

    __tablename__ = "card_questions"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class CardMerge(Base, CreatedMixin):
    __tablename__ = "card_merges"
    __table_args__ = (CheckConstraint("alias_id != canonical_id"),)

    alias_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"), primary_key=True)
    canonical_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"), index=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)


class CardOriginal(Base, CreatedMixin):
    __tablename__ = "card_originals"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"), primary_key=True)
    data: Mapped[dict] = mapped_column(JsonType)


class CardRelation(Base, CreatedMixin):
    __tablename__ = "card_relations"
    __table_args__ = (CheckConstraint("left_id < right_id"),)

    left_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"), primary_key=True)
    right_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="RESTRICT"), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    batch_id: Mapped[str] = mapped_column(String(64), index=True)


class PlanDay(Base):
    """学习计划课表（旧版硬编码在 PLAN_DAYS）。"""

    __tablename__ = "plan_days"

    day_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))


class PlanDayPart(Base):
    __tablename__ = "plan_day_parts"

    day_no: Mapped[int] = mapped_column(ForeignKey("plan_days.day_no", ondelete="CASCADE"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(32), primary_key=True)
    part: Mapped[str] = mapped_column(String(64), primary_key=True)
