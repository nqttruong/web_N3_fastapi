"""Knowledge extraction, review scheduling and practice generation (PR4).

Additive: extends knowledge_items, review_items, review_events (schema-only since PR1) and
adds knowledge_relations, knowledge_evidence, review_sessions, practice_generations,
generated_practice_questions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 22:54:49.634046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_sessions",
        sa.Column("cards", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(cards) = 'array'", name=op.f("ck_review_sessions_cards_is_array")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_sessions")),
    )
    op.create_table(
        "knowledge_evidence",
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("explanation_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("extracted", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('tests', 'distractor', 'context')",
            name=op.f("ck_knowledge_evidence_role_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["explanation_id"],
            ["ai_explanations.id"],
            name=op.f("fk_knowledge_evidence_explanation_id_ai_explanations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            name=op.f("fk_knowledge_evidence_knowledge_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_knowledge_evidence_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_evidence")),
        sa.UniqueConstraint(
            "knowledge_id", "question_id", "explanation_id", name="uq_knowledge_evidence_source"
        ),
    )
    op.create_index(
        "ix_knowledge_evidence_question_id", "knowledge_evidence", ["question_id"], unique=False
    )
    op.create_table(
        "knowledge_relations",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("source_explanation_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type = 'prerequisite' OR source_id < target_id",
            name=op.f("ck_knowledge_relations_symmetric_relations_ordered"),
        ),
        sa.CheckConstraint(
            "relation_type IN ('confused_with', 'prerequisite', 'related_to')",
            name=op.f("ck_knowledge_relations_relation_type_valid"),
        ),
        sa.CheckConstraint(
            "source_id <> target_id", name=op.f("ck_knowledge_relations_no_self_relation")
        ),
        sa.ForeignKeyConstraint(
            ["source_explanation_id"],
            ["ai_explanations.id"],
            name=op.f("fk_knowledge_relations_source_explanation_id_ai_explanations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_items.id"],
            name=op.f("fk_knowledge_relations_source_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["knowledge_items.id"],
            name=op.f("fk_knowledge_relations_target_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_relations")),
        sa.UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_knowledge_relations_pair"
        ),
    )
    op.create_index(
        "ix_knowledge_relations_target_id", "knowledge_relations", ["target_id"], unique=False
    )
    op.create_table(
        "practice_generations",
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("requested_count", sa.SmallInteger(), nullable=False),
        sa.Column("accepted_count", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "origin IN ('api', 'manual')", name=op.f("ck_practice_generations_origin_valid")
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'failed')",
            name=op.f("ck_practice_generations_status_valid"),
        ),
        sa.CheckConstraint(
            "accepted_count >= 0 AND accepted_count <= requested_count",
            name=op.f("ck_practice_generations_accepted_le_requested"),
        ),
        sa.CheckConstraint(
            "requested_count BETWEEN 1 AND 10",
            name=op.f("ck_practice_generations_requested_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            name=op.f("fk_practice_generations_knowledge_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_generations")),
    )
    op.create_index(
        "ix_practice_generations_knowledge_id",
        "practice_generations",
        ["knowledge_id"],
        unique=False,
    )
    op.create_table(
        "generated_practice_questions",
        sa.Column("generation_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("source_explanation_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="needs_review", nullable=False),
        sa.Column("question_type", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answer_index", sa.SmallInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "validation_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("times_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(options) = 'array' AND jsonb_array_length(options) BETWEEN 2 AND 6",
            name=op.f("ck_generated_practice_questions_options_array"),
        ),
        sa.CheckConstraint(
            "status = 'needs_review' OR reviewed_at IS NOT NULL",
            name=op.f("ck_generated_practice_questions_review_has_timestamp"),
        ),
        sa.CheckConstraint(
            "status IN ('needs_review', 'approved', 'rejected')",
            name=op.f("ck_generated_practice_questions_status_valid"),
        ),
        sa.CheckConstraint(
            "answer_index >= 0 AND answer_index < jsonb_array_length(options)",
            name=op.f("ck_generated_practice_questions_answer_in_range"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["practice_generations.id"],
            name=op.f("fk_generated_practice_questions_generation_id_practice_generations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            name=op.f("fk_generated_practice_questions_knowledge_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_explanation_id"],
            ["ai_explanations.id"],
            name=op.f("fk_generated_practice_questions_source_explanation_id_ai_explanations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_practice_questions")),
    )
    op.create_index(
        "ix_generated_practice_fingerprint",
        "generated_practice_questions",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_generated_practice_knowledge_status",
        "generated_practice_questions",
        ["knowledge_id", "status"],
        unique=False,
    )
    op.add_column("knowledge_items", sa.Column("canonical_key", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_items",
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_items", sa.Column("status", sa.Text(), server_default="active", nullable=False)
    )
    op.add_column("knowledge_items", sa.Column("merged_into_id", sa.UUID(), nullable=True))
    op.add_column("knowledge_items", sa.Column("source_explanation_id", sa.UUID(), nullable=True))
    op.add_column("knowledge_items", sa.Column("android_ref", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_items", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.drop_constraint(
        op.f("uq_knowledge_items_type_level_title"), "knowledge_items", type_="unique"
    )
    op.create_index(
        "ix_knowledge_items_type_status",
        "knowledge_items",
        ["knowledge_type", "status"],
        unique=False,
    )
    op.create_unique_constraint(
        op.f("uq_knowledge_items_android_ref"), "knowledge_items", ["android_ref"]
    )
    op.create_index(
        "uq_knowledge_items_type_key_active",
        "knowledge_items",
        ["knowledge_type", "canonical_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_foreign_key(
        op.f("fk_knowledge_items_merged_into_id_knowledge_items"),
        "knowledge_items",
        "knowledge_items",
        ["merged_into_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_knowledge_items_source_explanation_id_ai_explanations"),
        "knowledge_items",
        "ai_explanations",
        ["source_explanation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("review_events", sa.Column("request_id", sa.UUID(), nullable=True))
    op.add_column("review_events", sa.Column("session_id", sa.UUID(), nullable=True))
    op.add_column("review_events", sa.Column("card_kind", sa.Text(), nullable=True))
    op.add_column(
        "review_events", sa.Column("selected_answer_index", sa.SmallInteger(), nullable=True)
    )
    op.add_column("review_events", sa.Column("answer_correct", sa.Boolean(), nullable=True))
    op.add_column(
        "review_events",
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "review_events",
        sa.Column("next_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "review_events", sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("review_events", sa.Column("algorithm_version", sa.Text(), nullable=True))
    op.add_column("review_events", sa.Column("timezone", sa.Text(), nullable=True))
    op.create_index("ix_review_events_reviewed_at", "review_events", ["reviewed_at"], unique=False)
    op.create_unique_constraint(
        op.f("uq_review_events_request_id"), "review_events", ["request_id"]
    )
    op.create_foreign_key(
        op.f("fk_review_events_session_id_review_sessions"),
        "review_events",
        "review_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("review_items", sa.Column("review_type", sa.Text(), nullable=True))
    op.add_column("review_items", sa.Column("dedup_key", sa.Text(), nullable=True))
    op.add_column("review_items", sa.Column("related_knowledge_id", sa.UUID(), nullable=True))
    op.add_column(
        "review_items",
        sa.Column(
            "source_question_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("review_items", sa.Column("source_explanation_id", sa.UUID(), nullable=True))
    op.add_column(
        "review_items", sa.Column("srs_state", sa.Text(), server_default="new", nullable=False)
    )
    op.add_column("review_items", sa.Column("step_index", sa.SmallInteger(), nullable=True))
    op.add_column(
        "review_items",
        sa.Column("interval_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "review_items", sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "review_items", sa.Column("review_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "review_items", sa.Column("lapse_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "review_items",
        sa.Column("algorithm_version", sa.Text(), server_default="ladder-v1", nullable=False),
    )
    op.add_column(
        "review_items",
        sa.Column("ladder", sa.Text(), server_default="20m,1h,1d,2d,1w,2w,1mo", nullable=False),
    )
    op.add_column(
        "review_items", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.alter_column("review_items", "knowledge_id", existing_type=sa.UUID(), nullable=True)
    op.drop_index(op.f("uq_review_items_knowledge_id"), table_name="review_items")
    op.create_index("ix_review_items_knowledge_id", "review_items", ["knowledge_id"], unique=False)
    op.create_unique_constraint(op.f("uq_review_items_dedup_key"), "review_items", ["dedup_key"])
    op.create_foreign_key(
        op.f("fk_review_items_source_explanation_id_ai_explanations"),
        "review_items",
        "ai_explanations",
        ["source_explanation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_review_items_related_knowledge_id_knowledge_items"),
        "review_items",
        "knowledge_items",
        ["related_knowledge_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- backfill rows created before PR4 (tables were schema-only, normally empty) ---
    op.execute(
        "UPDATE knowledge_items SET canonical_key = 'legacy:' || id::text WHERE canonical_key IS NULL"
    )
    op.execute(
        "UPDATE review_items SET review_type = 'knowledge_recall', dedup_key = 'k:' || knowledge_id::text WHERE review_type IS NULL"
    )
    op.alter_column("knowledge_items", "canonical_key", nullable=False)
    op.alter_column("review_items", "review_type", nullable=False)
    op.alter_column("review_items", "dedup_key", nullable=False)

    # --- CHECK constraints on existing tables (not detected by autogenerate) ---
    op.create_check_constraint(
        op.f("ck_knowledge_items_status_valid"),
        "knowledge_items",
        "status IN ('active', 'archived', 'merged')",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_items_canonical_key_not_blank"),
        "knowledge_items",
        "length(btrim(canonical_key)) > 0",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_items_details_is_object"),
        "knowledge_items",
        "jsonb_typeof(details) = 'object'",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_items_merged_has_target"),
        "knowledge_items",
        "(status = 'merged') = (merged_into_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_review_items_review_type_valid"),
        "review_items",
        "review_type IN ('original_question', 'knowledge_recall', 'contrast')",
    )
    op.create_check_constraint(
        op.f("ck_review_items_srs_state_valid"),
        "review_items",
        "srs_state IN ('new', 'learning', 'review', 'mastered')",
    )
    op.create_check_constraint(
        op.f("ck_review_items_sources_is_array"),
        "review_items",
        "jsonb_typeof(source_question_ids) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_review_items_type_a_has_question"),
        "review_items",
        "review_type <> 'original_question' OR source_question_id IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_review_items_type_b_has_knowledge"),
        "review_items",
        "review_type <> 'knowledge_recall' OR knowledge_id IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_review_items_type_c_has_pair"),
        "review_items",
        "review_type <> 'contrast' OR (knowledge_id IS NOT NULL AND related_knowledge_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_review_items_new_items_have_no_step"),
        "review_items",
        "(step_index IS NULL) = (srs_state = 'new')",
    )
    op.create_check_constraint(
        op.f("ck_review_items_counters_non_negative"),
        "review_items",
        "review_count >= 0 AND lapse_count >= 0 AND interval_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_review_items_counters_non_negative"), "review_items", type_="check")
    op.drop_constraint(
        op.f("ck_review_items_new_items_have_no_step"), "review_items", type_="check"
    )
    op.drop_constraint(op.f("ck_review_items_type_c_has_pair"), "review_items", type_="check")
    op.drop_constraint(op.f("ck_review_items_type_b_has_knowledge"), "review_items", type_="check")
    op.drop_constraint(op.f("ck_review_items_type_a_has_question"), "review_items", type_="check")
    op.drop_constraint(op.f("ck_review_items_sources_is_array"), "review_items", type_="check")
    op.drop_constraint(op.f("ck_review_items_srs_state_valid"), "review_items", type_="check")
    op.drop_constraint(op.f("ck_review_items_review_type_valid"), "review_items", type_="check")
    op.drop_constraint(
        op.f("ck_knowledge_items_merged_has_target"), "knowledge_items", type_="check"
    )
    op.drop_constraint(
        op.f("ck_knowledge_items_details_is_object"), "knowledge_items", type_="check"
    )
    op.drop_constraint(
        op.f("ck_knowledge_items_canonical_key_not_blank"), "knowledge_items", type_="check"
    )
    op.drop_constraint(op.f("ck_knowledge_items_status_valid"), "knowledge_items", type_="check")
    # PR1 allowed one review item per knowledge item: keep only the oldest per knowledge before restoring it.
    op.execute(
        "DELETE FROM review_items WHERE knowledge_id IS NULL OR id NOT IN (SELECT DISTINCT ON (knowledge_id) id FROM review_items WHERE knowledge_id IS NOT NULL ORDER BY knowledge_id, created_at)"
    )
    op.drop_constraint(
        op.f("fk_review_items_related_knowledge_id_knowledge_items"),
        "review_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_review_items_source_explanation_id_ai_explanations"),
        "review_items",
        type_="foreignkey",
    )
    op.drop_constraint(op.f("uq_review_items_dedup_key"), "review_items", type_="unique")
    op.drop_index("ix_review_items_knowledge_id", table_name="review_items")
    op.create_index(
        op.f("uq_review_items_knowledge_id"), "review_items", ["knowledge_id"], unique=True
    )
    op.alter_column("review_items", "knowledge_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("review_items", "version")
    op.drop_column("review_items", "ladder")
    op.drop_column("review_items", "algorithm_version")
    op.drop_column("review_items", "lapse_count")
    op.drop_column("review_items", "review_count")
    op.drop_column("review_items", "last_reviewed_at")
    op.drop_column("review_items", "interval_minutes")
    op.drop_column("review_items", "step_index")
    op.drop_column("review_items", "srs_state")
    op.drop_column("review_items", "source_explanation_id")
    op.drop_column("review_items", "source_question_ids")
    op.drop_column("review_items", "related_knowledge_id")
    op.drop_column("review_items", "dedup_key")
    op.drop_column("review_items", "review_type")
    op.drop_constraint(
        op.f("fk_review_events_session_id_review_sessions"), "review_events", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_review_events_request_id"), "review_events", type_="unique")
    op.drop_index("ix_review_events_reviewed_at", table_name="review_events")
    op.drop_column("review_events", "timezone")
    op.drop_column("review_events", "algorithm_version")
    op.drop_column("review_events", "next_due_at")
    op.drop_column("review_events", "next_state")
    op.drop_column("review_events", "previous_state")
    op.drop_column("review_events", "answer_correct")
    op.drop_column("review_events", "selected_answer_index")
    op.drop_column("review_events", "card_kind")
    op.drop_column("review_events", "session_id")
    op.drop_column("review_events", "request_id")
    op.drop_constraint(
        op.f("fk_knowledge_items_source_explanation_id_ai_explanations"),
        "knowledge_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_knowledge_items_merged_into_id_knowledge_items"),
        "knowledge_items",
        type_="foreignkey",
    )
    op.drop_index(
        "uq_knowledge_items_type_key_active",
        table_name="knowledge_items",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_constraint(op.f("uq_knowledge_items_android_ref"), "knowledge_items", type_="unique")
    op.drop_index("ix_knowledge_items_type_status", table_name="knowledge_items")
    op.create_unique_constraint(
        op.f("uq_knowledge_items_type_level_title"),
        "knowledge_items",
        ["knowledge_type", "jlpt_level", "title"],
        postgresql_nulls_not_distinct=False,
    )
    op.drop_column("knowledge_items", "version")
    op.drop_column("knowledge_items", "android_ref")
    op.drop_column("knowledge_items", "source_explanation_id")
    op.drop_column("knowledge_items", "merged_into_id")
    op.drop_column("knowledge_items", "status")
    op.drop_column("knowledge_items", "details")
    op.drop_column("knowledge_items", "canonical_key")
    op.drop_index(
        "ix_generated_practice_knowledge_status", table_name="generated_practice_questions"
    )
    op.drop_index("ix_generated_practice_fingerprint", table_name="generated_practice_questions")
    op.drop_table("generated_practice_questions")
    op.drop_index("ix_practice_generations_knowledge_id", table_name="practice_generations")
    op.drop_table("practice_generations")
    op.drop_index("ix_knowledge_relations_target_id", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
    op.drop_index("ix_knowledge_evidence_question_id", table_name="knowledge_evidence")
    op.drop_table("knowledge_evidence")
    op.drop_table("review_sessions")
