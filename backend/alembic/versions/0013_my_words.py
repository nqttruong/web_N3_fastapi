"""Personal words, append-only review events, and scoped extension credentials.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "my_words",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("fingerprint", sa.Text(), nullable=False, unique=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("meanings", postgresql.JSONB(), nullable=False),
        sa.Column("japanese_reading", sa.Text()),
        sa.Column("english_ipa", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_title", sa.Text()),
        sa.Column("context", sa.Text()),
        sa.Column(
            "tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("language IN ('ja','en','vi')", name="my_word_language_valid"),
    )
    op.create_index("ix_my_words_language_active", "my_words", ["language", "archived_at"])
    op.create_table(
        "my_word_progress",
        sa.Column(
            "word_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("my_words.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("lapse_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "my_word_review_events",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "word_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("my_words.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at_after", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "my_word_extension_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("my_word_extension_credentials")
    op.drop_table("my_word_review_events")
    op.drop_table("my_word_progress")
    op.drop_index("ix_my_words_language_active", table_name="my_words")
    op.drop_table("my_words")
