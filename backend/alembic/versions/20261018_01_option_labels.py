"""Add explicit source option labels without rewriting old question answers.

Revision ID: 20261018_01
Revises: 20261017_sync
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261018_01"
down_revision = "20261017_sync"
branch_labels = None
depends_on = None


def upgrade():
    # [] explicitly means legacy contiguous fallback; no guessed source labels.
    op.add_column("questions", sa.Column("option_labels", sa.JSON().with_variant(JSONB(), "postgresql"),
                                        nullable=False, server_default=sa.text("'[]'")))
    with op.batch_alter_table("attempts") as batch:
        batch.alter_column("picked", existing_type=sa.String(16), type_=sa.String(26), existing_nullable=False)


def downgrade():
    # Intentionally retain the widened attempts.picked column: narrowing after
    # real 17-26 choice answers exist would reject/truncate historical records.
    op.drop_column("questions", "option_labels")
