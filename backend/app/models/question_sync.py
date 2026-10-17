"""Upstream records, immutable revisions and explicitly reviewed publications."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, JsonType


class SyncCursor(Base):
    __tablename__ = "sync_cursors"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope: Mapped[str] = mapped_column(String(160), primary_key=True)
    next_id: Mapped[int] = mapped_column(default=1)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncRun(Base, CreatedMixin):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="running")
    counts: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncDocument(Base):
    __tablename__ = "sync_documents"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_sync_document"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(32))
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"))
    latest_version: Mapped[int] = mapped_column(default=0)
    published_version: Mapped[int | None] = mapped_column()
    latest_hash: Mapped[str] = mapped_column(String(64), default="")
    raw: Mapped[dict] = mapped_column(JsonType, default=dict)
    validation_error: Mapped[str] = mapped_column(Text, default="")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncRevision(Base, CreatedMixin):
    __tablename__ = "sync_revisions"
    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_sync_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("sync_documents.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column()
    digest: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict] = mapped_column(JsonType)
    normalized: Mapped[dict] = mapped_column(JsonType)
    source_meta: Mapped[dict] = mapped_column(JsonType)
    analysis_attempts: Mapped[int] = mapped_column(default=0)
    analysis_error: Mapped[str] = mapped_column(Text, default="")


class SyncProposal(Base, CreatedMixin):
    __tablename__ = "sync_proposals"
    __table_args__ = (
        UniqueConstraint("revision_id", name="uq_sync_proposal_revision"),
        CheckConstraint("status IN ('pending','applied','rejected')", name="ck_sync_proposal_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("sync_revisions.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    local_snapshot: Mapped[dict] = mapped_column(JsonType, default=dict)
    context: Mapped[dict] = mapped_column(JsonType, default=dict)
    suggestion: Mapped[dict] = mapped_column(JsonType, default=dict)
    digest: Mapped[str] = mapped_column(String(64))
    decision: Mapped[dict] = mapped_column(JsonType, default=dict)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncClassificationRule(Base):
    __tablename__ = "sync_classification_rules"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    bank_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    chapter_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    bank_group: Mapped[str] = mapped_column(String(64))
    subject_dir: Mapped[str] = mapped_column(String(32))
    system: Mapped[str] = mapped_column(String(64))
    proposal_id: Mapped[int] = mapped_column(ForeignKey("sync_proposals.id", ondelete="RESTRICT"))
