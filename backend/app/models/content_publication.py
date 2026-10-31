from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, JsonType


class ChapterTextbookPage(Base):
    __tablename__ = 'chapter_textbook_pages'
    __table_args__ = (UniqueConstraint('chapter_id', 'source_key', 'page', name='uq_chapter_textbook_page'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey('chapters.id', ondelete='CASCADE'), index=True)
    source_key: Mapped[str] = mapped_column(ForeignKey('textbook_sources.key', ondelete='RESTRICT'), index=True)
    page: Mapped[int] = mapped_column(Integer)


class ContentPublication(Base):
    __tablename__ = 'content_publications'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CitationMetadataHistory(Base):
    __tablename__ = 'citation_metadata_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    citation_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(100))
    previous: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
