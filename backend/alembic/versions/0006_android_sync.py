"""Add paired devices, an idempotent Android review inbox and a trigger-backed change feed.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_devices")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sync_devices_token_hash")),
    )
    op.create_table(
        "android_review_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_before_minutes", sa.BigInteger(), nullable=False),
        sa.Column("interval_after_minutes", sa.BigInteger(), nullable=False),
        sa.Column("due_at_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "item_type IN ('VOCABULARY', 'KANJI', 'GRAMMAR')",
            name=op.f("ck_android_review_events_item_type_valid"),
        ),
        sa.CheckConstraint(
            "rating IN ('AGAIN', 'HARD', 'GOOD', 'EASY')",
            name=op.f("ck_android_review_events_rating_valid"),
        ),
        sa.CheckConstraint(
            "interval_before_minutes >= 0 AND interval_after_minutes >= 0",
            name=op.f("ck_android_review_events_interval_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["sync_devices.id"],
            ondelete="RESTRICT",
            name=op.f("fk_android_review_events_device_id_sync_devices"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_android_review_events")),
        sa.UniqueConstraint("request_id", name=op.f("uq_android_review_events_request_id")),
    )
    op.create_index(
        "ix_android_review_events_item_time",
        "android_review_events",
        ["item_type", "item_id", "reviewed_at"],
    )
    op.drop_constraint(op.f("ck_sync_changes_entity_type_valid"), "sync_changes", type_="check")
    op.create_check_constraint(
        op.f("ck_sync_changes_entity_type_valid"),
        "sync_changes",
        "entity_type IN ('exam', 'passage', 'question', 'exam_attempt', 'attempt_answer', 'knowledge_item', 'question_knowledge', 'review_item', 'review_event', 'ai_explanation', 'android_review_event')",
    )
    op.execute("""
    CREATE FUNCTION record_sync_change() RETURNS trigger AS $$
    DECLARE row_id uuid; entity text; ver bigint; op_kind text;
    BEGIN
      entity := TG_ARGV[0];
      IF TG_OP = 'DELETE' THEN row_id := OLD.id; op_kind := 'delete';
      ELSE row_id := NEW.id; op_kind := CASE WHEN TG_OP = 'INSERT' THEN 'insert' ELSE 'update' END;
      END IF;
      SELECT COALESCE(MAX(version), 0) + 1 INTO ver FROM sync_changes WHERE entity_type = entity AND entity_id = row_id;
      INSERT INTO sync_changes(entity_type, entity_id, operation, version) VALUES (entity, row_id, op_kind, ver);
      IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END; $$ LANGUAGE plpgsql;
    """)
    for table, entity in (
        ("exams", "exam"),
        ("passages", "passage"),
        ("questions", "question"),
        ("ai_explanations", "ai_explanation"),
    ):
        op.execute(
            f"CREATE TRIGGER {table}_sync_change AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION record_sync_change('{entity}')"
        )
    # Seed an initial snapshot through the same ordered feed without modifying business rows.
    for table, entity in (
        ("exams", "exam"),
        ("passages", "passage"),
        ("questions", "question"),
        ("ai_explanations", "ai_explanation"),
    ):
        op.execute(
            f"INSERT INTO sync_changes(entity_type, entity_id, operation, version) SELECT '{entity}', id, 'insert', 1 FROM {table}"
        )


def downgrade() -> None:
    for table in ("exams", "passages", "questions", "ai_explanations"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_sync_change ON {table}")
    op.execute("DROP FUNCTION IF EXISTS record_sync_change()")
    op.drop_constraint(op.f("ck_sync_changes_entity_type_valid"), "sync_changes", type_="check")
    # Feed entries for types introduced by this revision cannot satisfy the old schema check.
    op.execute(
        "DELETE FROM sync_changes WHERE entity_type IN ('ai_explanation', 'android_review_event')"
    )
    op.create_check_constraint(
        op.f("ck_sync_changes_entity_type_valid"),
        "sync_changes",
        "entity_type IN ('exam', 'passage', 'question', 'exam_attempt', 'attempt_answer', 'knowledge_item', 'question_knowledge', 'review_item', 'review_event')",
    )
    op.drop_index("ix_android_review_events_item_time", table_name="android_review_events")
    op.drop_table("android_review_events")
    op.drop_table("sync_devices")
