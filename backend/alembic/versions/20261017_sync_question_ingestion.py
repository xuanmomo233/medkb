"""Stage upstream question versions and explicitly reviewed AI suggestions.

Revision ID: 20261017_sync
Revises: 20261017_02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261017_sync"
down_revision = "20261017_02"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    created = lambda: sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    op.create_table("sync_cursors",
        sa.Column("source", sa.String(32), primary_key=True), sa.Column("scope", sa.String(160), primary_key=True),
        sa.Column("next_id", sa.Integer(), nullable=False), sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.create_table("sync_runs", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False), sa.Column("scope", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("counts", json_type, nullable=False),
        sa.Column("error", sa.Text(), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)), created())
    op.create_table("sync_documents", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False), sa.Column("external_id", sa.String(32), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT")),
        sa.Column("latest_version", sa.Integer(), nullable=False), sa.Column("published_version", sa.Integer()),
        sa.Column("latest_hash", sa.String(64), nullable=False), sa.Column("raw", json_type, nullable=False),
        sa.Column("validation_error", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_sync_document"))
    op.create_table("sync_revisions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("sync_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("raw", json_type, nullable=False), sa.Column("normalized", json_type, nullable=False),
        sa.Column("source_meta", json_type, nullable=False),
        sa.Column("local_baseline", json_type, nullable=False),
        sa.Column("analysis_attempts", sa.Integer(), nullable=False), sa.Column("analysis_error", sa.Text(), nullable=False), created(),
        sa.UniqueConstraint("document_id", "version", name="uq_sync_revision"))
    op.create_index("ix_sync_revisions_document_id", "sync_revisions", ["document_id"])
    op.create_table("sync_proposals", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("sync_revisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("local_snapshot", json_type, nullable=False),
        sa.Column("context", json_type, nullable=False), sa.Column("suggestion", json_type, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False), sa.Column("decision", json_type, nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)), created(),
        sa.UniqueConstraint("revision_id", name="uq_sync_proposal_revision"),
        sa.CheckConstraint("status IN ('pending','applied','rejected')", name="ck_sync_proposal_status"))
    op.create_index("ix_sync_proposals_status", "sync_proposals", ["status"])
    op.create_table("sync_classification_rules",
        sa.Column("source", sa.String(32), primary_key=True), sa.Column("bank_id", sa.String(32), primary_key=True),
        sa.Column("chapter_id", sa.String(32), primary_key=True), sa.Column("bank_group", sa.String(64), nullable=False),
        sa.Column("subject_dir", sa.String(32), nullable=False), sa.Column("system", sa.String(64), nullable=False),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("sync_proposals.id", ondelete="RESTRICT"), nullable=False))


def downgrade():
    for table in ("sync_classification_rules", "sync_proposals", "sync_revisions", "sync_documents", "sync_runs", "sync_cursors"):
        op.drop_table(table)
