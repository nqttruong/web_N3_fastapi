"""Persist source grammar exercise answers without touching SRS or Android state.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_exercise_answers",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("exercise_id", sa.Text(), nullable=False),
        sa.Column("selected_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("source_content_hash", sa.Text(), nullable=False),
        sa.Column("exercise_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_learning_exercise_answers_item_time",
        "learning_exercise_answers",
        ["item_id", "answered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_exercise_answers_item_time", table_name="learning_exercise_answers")
    op.drop_table("learning_exercise_answers")
