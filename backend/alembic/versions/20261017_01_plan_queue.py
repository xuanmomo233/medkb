"""Add fixed plan tasks and empty, explicitly maintained question relationships.

Revision ID: 20261017_01
Revises: 20261016_02
"""

from alembic import op
import sqlalchemy as sa

revision = "20261017_01"
down_revision = "20261016_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("question_merges",
        sa.Column("alias_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("canonical_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("alias_id <> canonical_id", name="ck_question_merge_distinct"))
    op.create_index("ix_question_merges_canonical_id", "question_merges", ["canonical_id"])
    op.create_table("question_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("left_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("right_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("left_id", "right_id", "kind", name="uq_question_relation"),
        sa.CheckConstraint("left_id < right_id", name="ck_question_relation_order"),
        sa.CheckConstraint("kind IN ('variant', 'same_concept', 'contrast')", name="ck_question_relation_kind"))
    for side in ("left", "right"):
        op.create_index(f"ix_question_relations_{side}_id", "question_relations", [f"{side}_id"])
    op.create_table("plan_snapshots",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_plans.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("plan_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_plans.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("due_day", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "kind", "target_id", name="uq_plan_task_target"),
        sa.CheckConstraint("kind IN ('question', 'card')", name="ck_plan_task_kind"))
    op.create_index("ix_plan_tasks_user_id", "plan_tasks", ["user_id"])
    op.create_index("ix_plan_tasks_pending", "plan_tasks", ["user_id", "kind", "due_day", "completed_at"])
    op.create_table("plan_task_sections",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("plan_tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("subject", sa.String(64), primary_key=True),
        sa.Column("part", sa.String(64), primary_key=True))


def downgrade() -> None:
    for name in ("plan_task_sections", "plan_tasks", "plan_snapshots", "question_relations", "question_merges"):
        op.drop_table(name)
