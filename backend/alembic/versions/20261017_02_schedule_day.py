"""Freeze each daily schedule, including an empty day.

Revision ID: 20261017_02
Revises: 20261017_01
"""

from alembic import op
import sqlalchemy as sa

revision = "20261017_02"
down_revision = "20261017_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("schedule_days",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_table("schedule_days")
