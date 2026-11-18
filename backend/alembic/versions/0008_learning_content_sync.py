"""Add read-only Android learning content mirrors and sync audit tables.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_content_sync_queue_lock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_sync_queue_lock")),
        sa.CheckConstraint("id = 1", name=op.f("ck_learning_content_sync_queue_lock_singleton")),
    )
    op.execute("INSERT INTO learning_content_sync_queue_lock (id) VALUES (1)")
    op.create_table(
        "learning_content_packs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("jlpt_level", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("source_commit_sha", sa.Text(), nullable=True),
        sa.Column("source_manifest_hash", sa.Text(), nullable=False),
        sa.Column("license_blocked_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_packs")),
        sa.UniqueConstraint("source_path", name=op.f("uq_learning_content_packs_source_path")),
    )
    op.create_table(
        "learning_content_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("source_commit_sha", sa.Text(), nullable=True),
        sa.Column("source_manifest_hash", sa.Text(), nullable=True),
        sa.Column(
            "counts", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'no_changes', 'failed')",
            name=op.f("ck_learning_content_sync_runs_learning_sync_status_valid"),
        ),
        sa.CheckConstraint(
            "trigger IN ('startup', 'interval', 'manual')",
            name=op.f("ck_learning_content_sync_runs_learning_sync_trigger_valid"),
        ),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 3",
            name=op.f("ck_learning_content_sync_runs_learning_sync_attempts_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_sync_runs")),
    )
    op.create_index(
        "ix_learning_sync_runs_requested", "learning_content_sync_runs", ["status", "requested_at"]
    )
    op.create_table(
        "learning_content_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "number > 0 AND order_index >= 0",
            name=op.f("ck_learning_content_lessons_lesson_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["learning_content_packs.id"],
            ondelete="RESTRICT",
            name=op.f("fk_learning_content_lessons_pack_id_learning_content_packs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_lessons")),
        sa.UniqueConstraint("pack_id", "source_id", name=op.f("uq_learning_lessons_pack_source")),
        sa.UniqueConstraint("pack_id", "number", name=op.f("uq_learning_lessons_pack_number")),
        sa.UniqueConstraint("pack_id", "id", name=op.f("uq_learning_lessons_pack_id_id")),
    )
    op.create_index(
        "ix_learning_lessons_pack_order", "learning_content_lessons", ["pack_id", "order_index"]
    )
    op.create_table(
        "learning_content_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["learning_content_packs.id"],
            ondelete="RESTRICT",
            name=op.f("fk_learning_content_examples_pack_id_learning_content_packs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_examples")),
        sa.UniqueConstraint("pack_id", "source_ref", name=op.f("uq_learning_examples_pack_source")),
        sa.UniqueConstraint("pack_id", "id", name=op.f("uq_learning_examples_pack_id_id")),
    )
    op.create_index("ix_learning_examples_pack", "learning_content_examples", ["pack_id"])
    op.create_table(
        "learning_content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("jlpt_level", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_license", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('vocabulary', 'kanji', 'grammar')",
            name=op.f("ck_learning_content_items_learning_item_type_valid"),
        ),
        sa.CheckConstraint(
            "order_index >= 0", name=op.f("ck_learning_content_items_learning_item_order_valid")
        ),
        sa.ForeignKeyConstraint(
            ["pack_id", "lesson_id"],
            ["learning_content_lessons.pack_id", "learning_content_lessons.id"],
            ondelete="RESTRICT",
            name="fk_learning_items_pack_lesson",
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["learning_content_packs.id"],
            ondelete="RESTRICT",
            name=op.f("fk_learning_content_items_pack_id_learning_content_packs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_items")),
        sa.UniqueConstraint(
            "pack_id", "item_type", "source_ref", name=op.f("uq_learning_items_source")
        ),
        sa.UniqueConstraint("pack_id", "id", name=op.f("uq_learning_items_pack_id_id")),
    )
    op.create_index(
        "ix_learning_items_type_level",
        "learning_content_items",
        ["item_type", "jlpt_level", "is_archived"],
    )
    op.create_index(
        "ix_learning_items_lesson_order", "learning_content_items", ["lesson_id", "order_index"]
    )
    op.create_table(
        "learning_content_item_examples",
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("example_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "order_index >= 0",
            name=op.f("ck_learning_content_item_examples_learning_example_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["pack_id", "example_id"],
            ["learning_content_examples.pack_id", "learning_content_examples.id"],
            ondelete="RESTRICT",
            name="fk_learning_item_examples_pack_example",
        ),
        sa.ForeignKeyConstraint(
            ["pack_id", "item_id"],
            ["learning_content_items.pack_id", "learning_content_items.id"],
            ondelete="RESTRICT",
            name="fk_learning_item_examples_pack_item",
        ),
        sa.PrimaryKeyConstraint(
            "item_id", "example_id", name=op.f("pk_learning_content_item_examples")
        ),
    )
    op.create_table(
        "learning_content_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("old_hash", sa.Text(), nullable=True),
        sa.Column("new_hash", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "entity_type IN ('pack', 'lesson', 'example', 'vocabulary', 'kanji', 'grammar')",
            name=op.f("ck_learning_content_changes_learning_change_entity_valid"),
        ),
        sa.CheckConstraint(
            "change_type IN ('created', 'updated', 'archived', 'restored')",
            name=op.f("ck_learning_content_changes_learning_change_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["learning_content_sync_runs.id"],
            ondelete="RESTRICT",
            name=op.f("fk_learning_content_changes_run_id_learning_content_sync_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["learning_content_packs.id"],
            ondelete="RESTRICT",
            name="fk_learning_changes_pack",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_content_changes")),
    )
    op.create_index("ix_learning_changes_run", "learning_content_changes", ["run_id", "changed_at"])
    op.create_index(
        "ix_learning_changes_source",
        "learning_content_changes",
        ["pack_id", "entity_type", "source_ref"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_changes_source", table_name="learning_content_changes")
    op.drop_index("ix_learning_changes_run", table_name="learning_content_changes")
    op.drop_table("learning_content_changes")
    op.drop_table("learning_content_item_examples")
    op.drop_index("ix_learning_items_lesson_order", table_name="learning_content_items")
    op.drop_index("ix_learning_items_type_level", table_name="learning_content_items")
    op.drop_table("learning_content_items")
    op.drop_index("ix_learning_examples_pack", table_name="learning_content_examples")
    op.drop_table("learning_content_examples")
    op.drop_index("ix_learning_lessons_pack_order", table_name="learning_content_lessons")
    op.drop_table("learning_content_lessons")
    op.drop_index("ix_learning_sync_runs_requested", table_name="learning_content_sync_runs")
    op.drop_table("learning_content_sync_runs")
    op.drop_table("learning_content_packs")
    op.drop_table("learning_content_sync_queue_lock")
