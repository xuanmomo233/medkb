"""add structured textbook provenance

Revision ID: 20261016_01
Revises:
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20261016_01"
down_revision = None
branch_labels = None
depends_on = None

TEXTBOOKS = (
    ("rjws-physiology-10", "生理学", "生理学"),
    ("rjws-biochemistry-10", "生物化学与分子生物学", "生物化学"),
    ("rjws-pathology-10", "病理学", "病理学"),
    ("rjws-diagnostics-10", "诊断学", "诊断学"),
    ("rjws-internal-medicine-10", "内科学", "内科学"),
    ("rjws-surgery-10", "外科学", "外科学"),
)


def upgrade() -> None:
    op.create_table(
        "textbook_sources",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("publisher", sa.String(100), nullable=False, server_default="人民卫生出版社"),
        sa.Column("edition", sa.String(32), nullable=False, server_default="第十版"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_textbook_sources_subject", "textbook_sources", ["subject"])
    op.create_index("ix_textbook_sources_active", "textbook_sources", ["active"])
    source_table = sa.table(
        "textbook_sources", sa.column("key"), sa.column("title"), sa.column("subject"),
        sa.column("publisher"), sa.column("edition"), sa.column("active"),
    )
    op.bulk_insert(source_table, [
        {"key": key, "title": title, "subject": subject, "publisher": "人民卫生出版社",
         "edition": "第十版", "active": True}
        for key, title, subject in TEXTBOOKS
    ])
    op.create_table(
        "content_citations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(64), sa.ForeignKey("textbook_sources.key", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter", sa.String(200), nullable=False, server_default=""),
        sa.Column("section", sa.String(200), nullable=False, server_default=""),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("target_type IN ('chapter', 'question', 'card')", name="ck_citation_target_type"),
        sa.CheckConstraint("status IN ('unverified', 'verified', 'disputed')", name="ck_citation_status"),
        sa.CheckConstraint("page_start IS NULL OR page_start > 0", name="ck_citation_page_start"),
        sa.CheckConstraint("page_end IS NULL OR page_end > 0", name="ck_citation_page_end"),
        sa.CheckConstraint("page_end IS NULL OR page_start IS NOT NULL", name="ck_citation_page_pair"),
        sa.CheckConstraint("page_end IS NULL OR page_end >= page_start", name="ck_citation_page_order"),
        sa.UniqueConstraint(
            "target_type", "target_id", "source_key", "chapter", "section", "page_start", "page_end",
            name="uq_content_citation_location",
        ),
    )
    op.create_index("ix_content_citation_target", "content_citations", ["target_type", "target_id"])
    op.create_index("ix_content_citations_source_key", "content_citations", ["source_key"])
    op.create_index("ix_content_citations_status", "content_citations", ["status"])
    op.create_index("ix_content_citations_verified_by", "content_citations", ["verified_by"])


def downgrade() -> None:
    op.drop_table("content_citations")
    op.drop_table("textbook_sources")
