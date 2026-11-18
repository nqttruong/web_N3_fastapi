"""Add commit-ordered sync snapshots and capture all Android content/review entities.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sync_changes",
        sa.Column("schema_version", sa.Text(), server_default="1.0", nullable=False),
    )
    op.add_column("sync_changes", sa.Column("payload", postgresql.JSONB(), nullable=True))
    op.execute("ALTER TABLE sync_changes ALTER COLUMN id DROP IDENTITY IF EXISTS")
    op.create_table("sync_cursor_lock", sa.Column("id", sa.SmallInteger(), primary_key=True))
    op.execute("INSERT INTO sync_cursor_lock(id) VALUES (1)")
    op.execute("CREATE SEQUENCE sync_changes_cursor_seq AS bigint")
    op.execute(
        "SELECT setval('sync_changes_cursor_seq', COALESCE((SELECT max(id) FROM sync_changes), 0) + 1, false)"
    )
    op.execute("""
    CREATE FUNCTION next_sync_cursor() RETURNS bigint AS $$
    BEGIN
      PERFORM id FROM sync_cursor_lock WHERE id = 1 FOR UPDATE;
      RETURN nextval('sync_changes_cursor_seq');
    END; $$ LANGUAGE plpgsql VOLATILE;
    """)
    op.execute("ALTER TABLE sync_changes ALTER COLUMN id SET DEFAULT next_sync_cursor()")

    op.drop_constraint(op.f("ck_sync_changes_entity_type_valid"), "sync_changes", type_="check")
    op.create_check_constraint(
        op.f("ck_sync_changes_entity_type_valid"),
        "sync_changes",
        "entity_type IN ('exam', 'passage', 'question', 'exam_attempt', 'attempt_answer', 'knowledge_item', 'question_knowledge', 'review_item', 'review_event', 'ai_explanation', 'android_review_event')",
    )
    op.drop_constraint(
        op.f("ck_android_review_events_item_type_valid"), "android_review_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_android_review_events_item_type_valid"),
        "android_review_events",
        "item_type IN ('VOCABULARY', 'KANJI', 'GRAMMAR', 'JLPT_REVIEW_ITEM')",
    )

    for table in ("exams", "passages", "questions", "ai_explanations"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_sync_change ON {table}")

    op.execute("""
    CREATE OR REPLACE FUNCTION record_sync_change() RETURNS trigger AS $$
    DECLARE
      row_id uuid;
      entity text;
      ver bigint;
      op_kind text;
      row_payload jsonb;
      related_id uuid;
    BEGIN
      entity := TG_ARGV[0];
      IF TG_TABLE_NAME IN ('question_knowledge', 'knowledge_items') THEN
        IF TG_TABLE_NAME = 'knowledge_items' THEN
          IF TG_OP = 'DELETE' THEN related_id := OLD.id; ELSE related_id := NEW.id; END IF;
        ELSE
          IF TG_OP = 'DELETE' THEN related_id := OLD.knowledge_id; ELSE related_id := NEW.knowledge_id; END IF;
        END IF;
        row_id := related_id;
        entity := 'knowledge_item';
        SELECT to_jsonb(k) || jsonb_build_object(
          'linked_question_ids', COALESCE((SELECT jsonb_agg(qk.question_id::text ORDER BY qk.question_id)
            FROM question_knowledge qk WHERE qk.knowledge_id = related_id), '[]'::jsonb))
          INTO row_payload FROM knowledge_items k WHERE k.id = related_id;
        op_kind := CASE WHEN row_payload IS NULL THEN 'delete' ELSE 'update' END;
      ELSE
        IF TG_OP = 'DELETE' THEN row_id := OLD.id; op_kind := 'delete'; row_payload := NULL;
        ELSE row_id := NEW.id; row_payload := to_jsonb(NEW);
          op_kind := CASE WHEN TG_OP = 'INSERT' THEN 'insert' ELSE 'update' END;
        END IF;
      END IF;
      SELECT COALESCE(MAX(version), 0) + 1 INTO ver
        FROM sync_changes WHERE entity_type = entity AND entity_id = row_id;
      INSERT INTO sync_changes(entity_type, entity_id, operation, version, schema_version, payload)
        VALUES (entity, row_id, op_kind, ver, '1.0', row_payload);
      IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END; $$ LANGUAGE plpgsql;
    """)

    for table, entity in (
        ("exams", "exam"),
        ("passages", "passage"),
        ("questions", "question"),
        ("exam_attempts", "exam_attempt"),
        ("attempt_answers", "attempt_answer"),
        ("ai_explanations", "ai_explanation"),
        ("knowledge_items", "knowledge_item"),
        ("review_items", "review_item"),
        ("android_review_events", "android_review_event"),
    ):
        op.execute(
            f"CREATE TRIGGER {table}_sync_change AFTER INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION record_sync_change('{entity}')"
        )
    op.execute(
        "CREATE TRIGGER question_knowledge_sync_change AFTER INSERT OR UPDATE OR DELETE "
        "ON question_knowledge FOR EACH ROW EXECUTE FUNCTION record_sync_change('knowledge_item')"
    )
    # A question edit can make an already approved explanation stale without touching the
    # explanation row. Emit a fresh feed record so Android receives the API tombstone.
    op.execute("""
    CREATE FUNCTION invalidate_question_explanations() RETURNS trigger AS $$
    DECLARE ver bigint;
    BEGIN
      INSERT INTO sync_changes(entity_type, entity_id, operation, version, schema_version, payload)
      SELECT 'ai_explanation', e.id, 'update',
        COALESCE((SELECT max(c.version) FROM sync_changes c
          WHERE c.entity_type = 'ai_explanation' AND c.entity_id = e.id), 0) + 1,
        '1.0', to_jsonb(e)
      FROM ai_explanations e WHERE e.question_id = NEW.id;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER question_explanations_stale_sync AFTER UPDATE ON questions
      FOR EACH ROW EXECUTE FUNCTION invalidate_question_explanations();
    """)

    # Existing v6 feed rows already have cursor values. Backfill their immutable payloads in place.
    for table, entity in (
        ("exams", "exam"),
        ("passages", "passage"),
        ("questions", "question"),
        ("ai_explanations", "ai_explanation"),
    ):
        op.execute(
            f"UPDATE sync_changes c SET payload = to_jsonb(t), schema_version = '1.0' "
            f"FROM {table} t WHERE c.entity_type = '{entity}' AND c.entity_id = t.id"
        )
    op.execute(
        "UPDATE sync_changes c SET payload = to_jsonb(t), schema_version = '1.0' "
        "FROM android_review_events t WHERE c.entity_type = 'android_review_event' AND c.entity_id = t.id"
    )
    op.execute("""
    INSERT INTO sync_changes(entity_type, entity_id, operation, version, schema_version, payload)
    SELECT 'android_review_event', t.id, 'insert', 1, '1.0', to_jsonb(t)
    FROM android_review_events t
    WHERE NOT EXISTS (SELECT 1 FROM sync_changes c WHERE c.entity_type = 'android_review_event' AND c.entity_id = t.id)
    """)
    for table, entity in (
        ("exam_attempts", "exam_attempt"),
        ("attempt_answers", "attempt_answer"),
        ("review_items", "review_item"),
    ):
        op.execute(
            f"INSERT INTO sync_changes(entity_type, entity_id, operation, version, schema_version, payload) "
            f"SELECT '{entity}', t.id, 'insert', 1, '1.0', to_jsonb(t) FROM {table} t "
            f"WHERE NOT EXISTS (SELECT 1 FROM sync_changes c WHERE c.entity_type = '{entity}' AND c.entity_id = t.id)"
        )
    op.execute("""
    INSERT INTO sync_changes(entity_type, entity_id, operation, version, schema_version, payload)
    SELECT 'knowledge_item', k.id, 'insert', 1, '1.0', to_jsonb(k) || jsonb_build_object(
      'linked_question_ids', COALESCE((SELECT jsonb_agg(qk.question_id::text ORDER BY qk.question_id)
        FROM question_knowledge qk WHERE qk.knowledge_id = k.id), '[]'::jsonb))
    FROM knowledge_items k
    WHERE NOT EXISTS (SELECT 1 FROM sync_changes c WHERE c.entity_type = 'knowledge_item' AND c.entity_id = k.id)
    """)


def downgrade() -> None:
    for table in (
        "exams",
        "passages",
        "questions",
        "exam_attempts",
        "attempt_answers",
        "ai_explanations",
        "knowledge_items",
        "review_items",
        "android_review_events",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_sync_change ON {table}")
    op.execute("DROP TRIGGER IF EXISTS question_knowledge_sync_change ON question_knowledge")
    op.execute("DROP TRIGGER IF EXISTS question_explanations_stale_sync ON questions")
    op.execute("DROP FUNCTION IF EXISTS invalidate_question_explanations()")
    op.execute("DROP FUNCTION IF EXISTS record_sync_change()")
    op.drop_constraint(
        op.f("ck_android_review_events_item_type_valid"), "android_review_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_android_review_events_item_type_valid"),
        "android_review_events",
        "item_type IN ('VOCABULARY', 'KANJI', 'GRAMMAR')",
    )
    op.drop_constraint(op.f("ck_sync_changes_entity_type_valid"), "sync_changes", type_="check")
    op.create_check_constraint(
        op.f("ck_sync_changes_entity_type_valid"),
        "sync_changes",
        "entity_type IN ('exam', 'passage', 'question', 'exam_attempt', 'attempt_answer', 'knowledge_item', 'question_knowledge', 'review_item', 'review_event', 'ai_explanation', 'android_review_event')",
    )
    op.execute("ALTER TABLE sync_changes ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP FUNCTION IF EXISTS next_sync_cursor()")
    op.execute("DROP SEQUENCE IF EXISTS sync_changes_cursor_seq")
    op.drop_table("sync_cursor_lock")
    current = (
        op.get_bind()
        .execute(sa.text("SELECT COALESCE(max(id), 0) + 1 FROM sync_changes"))
        .scalar_one()
    )
    op.execute(
        f"ALTER TABLE sync_changes ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (START WITH {int(current)})"
    )
    op.drop_column("sync_changes", "payload")
    op.drop_column("sync_changes", "schema_version")
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
            f"CREATE TRIGGER {table}_sync_change AFTER INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION record_sync_change('{entity}')"
        )
