"""Add source-specific private rights and Web learning state.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_source_rights",
        sa.Column("pack_id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("rights_holder", sa.Text(), nullable=False),
        sa.Column("rights_basis", sa.Text(), nullable=False),
        sa.Column("allowed_usage", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text()),
        sa.Column("scope", sa.Text(), nullable=False, server_default="private"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "learning_study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("current_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "learning_study_progress",
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("lapse_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_learning_study_progress_due_at", "learning_study_progress", ["due_at"])
    op.create_table(
        "learning_saved_items",
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "saved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "learning_study_events",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_study_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_before_minutes", sa.Integer(), nullable=False),
        sa.Column("interval_after_minutes", sa.Integer(), nullable=False),
        sa.Column("due_at_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("was_new", sa.Boolean(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False, server_default="web"),
    )
    op.create_index(
        "ix_learning_study_events_item_time", "learning_study_events", ["item_id", "reviewed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_learning_study_events_item_time", table_name="learning_study_events")
    op.drop_table("learning_study_events")
    op.drop_table("learning_saved_items")
    op.drop_index("ix_learning_study_progress_due_at", table_name="learning_study_progress")
    op.drop_table("learning_study_progress")
    op.drop_table("learning_study_sessions")
    op.drop_table("learning_source_rights")
