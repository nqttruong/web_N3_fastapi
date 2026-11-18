"""Initial schema.

Exam content and attempts, plus schema-only tables for explanations, knowledge, reviews
and the sync change log.

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "exam_sources",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("base_url ~* '^https?://'", name=op.f("ck_exam_sources_base_url_http")),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_exam_sources_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_sources")),
        sa.UniqueConstraint("base_url", name=op.f("uq_exam_sources_base_url")),
        sa.UniqueConstraint("name", name=op.f("uq_exam_sources_name")),
    )
    op.create_table(
        "knowledge_items",
        sa.Column("knowledge_type", sa.Text(), nullable=False),
        sa.Column("jlpt_level", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
            "jlpt_level IN ('N1', 'N2', 'N3', 'N4', 'N5')",
            name=op.f("ck_knowledge_items_jlpt_level_valid"),
        ),
        sa.CheckConstraint(
            "knowledge_type IN ('vocabulary', 'kanji', 'grammar', 'reading_skill')",
            name=op.f("ck_knowledge_items_knowledge_type_valid"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("ck_knowledge_items_title_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_items")),
        sa.UniqueConstraint(
            "knowledge_type", "jlpt_level", "title", name="uq_knowledge_items_type_level_title"
        ),
    )
    op.create_table(
        "sync_changes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('exam', 'passage', 'question', 'exam_attempt', 'attempt_answer', 'knowledge_item', 'question_knowledge', 'review_item', 'review_event')",
            name=op.f("ck_sync_changes_entity_type_valid"),
        ),
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_sync_changes_operation_valid"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_sync_changes_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_changes")),
    )
    op.create_index("ix_sync_changes_changed_at", "sync_changes", ["changed_at"], unique=False)
    op.create_index(
        "uq_sync_changes_entity_version",
        "sync_changes",
        ["entity_type", "entity_id", "version"],
        unique=True,
    )
    op.create_table(
        "exams",
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
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
            "category IN ('vocabulary', 'kanji', 'grammar', 'reading')",
            name=op.f("ck_exams_category_valid"),
        ),
        sa.CheckConstraint(
            "level IN ('N1', 'N2', 'N3', 'N4', 'N5')", name=op.f("ck_exams_level_valid")
        ),
        sa.CheckConstraint(
            "source_url IS NULL OR source_url ~* '^https?://'",
            name=op.f("ck_exams_source_url_http"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'archived')", name=op.f("ck_exams_status_valid")
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name=op.f("ck_exams_title_not_blank")),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["exam_sources.id"],
            name=op.f("fk_exams_source_id_exam_sources"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exams")),
    )
    op.create_index("ix_exams_created_at", "exams", ["created_at"], unique=False)
    op.create_index("ix_exams_level_category", "exams", ["level", "category"], unique=False)
    op.create_index("ix_exams_source_id", "exams", ["source_id"], unique=False)
    op.create_index("ix_exams_status", "exams", ["status"], unique=False)
    op.create_index(
        "uq_exams_source_url",
        "exams",
        ["source_url"],
        unique=True,
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )
    op.create_table(
        "exam_attempts",
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("unanswered_count", sa.Integer(), nullable=False),
        sa.Column("ungraded_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name=op.f("ck_exam_attempts_completed_after_started"),
        ),
        sa.CheckConstraint(
            "correct_count + incorrect_count + unanswered_count + ungraded_count = total_questions",
            name=op.f("ck_exam_attempts_counts_sum_to_total"),
        ),
        sa.CheckConstraint(
            "correct_count >= 0 AND incorrect_count >= 0 AND unanswered_count >= 0 AND ungraded_count >= 0",
            name=op.f("ck_exam_attempts_counts_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name="fk_exam_attempts_exam_id_exams", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_attempts")),
        sa.UniqueConstraint("id", "exam_id", name="uq_exam_attempts_id_exam_id"),
    )
    op.create_index("ix_exam_attempts_exam_id", "exam_attempts", ["exam_id"], unique=False)
    op.create_index("ix_exam_attempts_started_at", "exam_attempts", ["started_at"], unique=False)
    op.create_table(
        "passages",
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(content)) > 0", name=op.f("ck_passages_content_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name=op.f("fk_passages_exam_id_exams"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_passages")),
        sa.UniqueConstraint("exam_id", "id", name="uq_passages_exam_id_id"),
    )
    op.create_index("ix_passages_exam_id", "passages", ["exam_id"], unique=False)
    op.create_table(
        "questions",
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("passage_id", sa.UUID(), nullable=True),
        sa.Column("question_number", sa.SmallInteger(), nullable=False),
        sa.Column("question_type", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_answer", sa.SmallInteger(), nullable=True),
        sa.Column("answer_status", sa.Text(), server_default="missing", nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
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
            "(answer_status = 'missing') = (correct_answer IS NULL)",
            name=op.f("ck_questions_answer_status_matches_answer"),
        ),
        sa.CheckConstraint(
            "answer_status IN ('missing', 'unverified', 'verified')",
            name=op.f("ck_questions_answer_status_valid"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(options) = 'array' AND jsonb_array_length(options) BETWEEN 2 AND 6",
            name=op.f("ck_questions_options_array_2_to_6"),
        ),
        sa.CheckConstraint(
            "question_type IN ('kanji_reading', 'orthography', 'word_formation', 'contextual_definition', 'paraphrase', 'usage', 'grammar_form', 'sentence_composition', 'text_grammar', 'reading_short', 'reading_medium', 'reading_long', 'information_retrieval', 'other')",
            name=op.f("ck_questions_question_type_valid"),
        ),
        sa.CheckConstraint(
            "correct_answer IS NULL OR (correct_answer >= 1 AND correct_answer <= jsonb_array_length(options))",
            name=op.f("ck_questions_correct_answer_in_range"),
        ),
        sa.CheckConstraint(
            "length(btrim(question_text)) > 0", name=op.f("ck_questions_question_text_not_blank")
        ),
        sa.CheckConstraint(
            "question_number > 0", name=op.f("ck_questions_question_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["exam_id", "passage_id"],
            ["passages.exam_id", "passages.id"],
            name="fk_questions_passage_same_exam",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name=op.f("fk_questions_exam_id_exams"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
        sa.UniqueConstraint("exam_id", "content_hash", name="uq_questions_exam_id_content_hash"),
        sa.UniqueConstraint("exam_id", "id", name="uq_questions_exam_id_id"),
        sa.UniqueConstraint(
            "exam_id", "question_number", name="uq_questions_exam_id_question_number"
        ),
    )
    op.create_index("ix_questions_passage_id", "questions", ["passage_id"], unique=False)
    op.create_table(
        "ai_explanations",
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verification_status", sa.Text(), server_default="unverified", nullable=False),
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
            "jsonb_typeof(explanation_json) = 'object'",
            name=op.f("ck_ai_explanations_explanation_is_object"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name=op.f("ck_ai_explanations_verification_status_valid"),
        ),
        sa.CheckConstraint(
            "length(btrim(provider)) > 0 AND length(btrim(model)) > 0",
            name=op.f("ck_ai_explanations_provider_model_set"),
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_ai_explanations_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_explanations")),
    )
    op.create_index(
        "ix_ai_explanations_question_id", "ai_explanations", ["question_id"], unique=False
    )
    op.create_table(
        "attempt_answers",
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_number", sa.SmallInteger(), nullable=False),
        sa.Column("selected_answer", sa.SmallInteger(), nullable=True),
        sa.Column("correct_answer_snapshot", sa.SmallInteger(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(is_correct IS NULL) = (selected_answer IS NULL OR correct_answer_snapshot IS NULL)",
            name=op.f("ck_attempt_answers_is_correct_consistent"),
        ),
        sa.CheckConstraint(
            "is_correct IS NULL OR is_correct = (selected_answer = correct_answer_snapshot)",
            name=op.f("ck_attempt_answers_is_correct_matches_snapshot"),
        ),
        sa.CheckConstraint(
            "selected_answer IS NULL OR selected_answer >= 1",
            name=op.f("ck_attempt_answers_selected_answer_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "exam_id"],
            ["exam_attempts.id", "exam_attempts.exam_id"],
            name="fk_attempt_answers_attempt_same_exam",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id", "question_id"],
            ["questions.exam_id", "questions.id"],
            name="fk_attempt_answers_question_same_exam",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attempt_answers")),
        sa.UniqueConstraint(
            "attempt_id", "question_id", name="uq_attempt_answers_attempt_question"
        ),
    )
    op.create_index(
        "ix_attempt_answers_question_id", "attempt_answers", ["question_id"], unique=False
    )
    op.create_table(
        "question_knowledge",
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN ('tests', 'distractor', 'context')",
            name=op.f("ck_question_knowledge_relation_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            name=op.f("fk_question_knowledge_knowledge_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_question_knowledge_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "knowledge_id", name=op.f("pk_question_knowledge")),
    )
    op.create_index(
        "ix_question_knowledge_knowledge_id", "question_knowledge", ["knowledge_id"], unique=False
    )
    op.create_table(
        "review_items",
        sa.Column("knowledge_id", sa.UUID(), nullable=False),
        sa.Column("source_question_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('active', 'suspended', 'done')", name=op.f("ck_review_items_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            name=op.f("fk_review_items_knowledge_id_knowledge_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_question_id"],
            ["questions.id"],
            name=op.f("fk_review_items_source_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_items")),
    )
    op.create_index(
        "ix_review_items_source_question_id", "review_items", ["source_question_id"], unique=False
    )
    op.create_index(
        "ix_review_items_status_due_at", "review_items", ["status", "due_at"], unique=False
    )
    op.create_index("uq_review_items_knowledge_id", "review_items", ["knowledge_id"], unique=True)
    op.create_table(
        "review_events",
        sa.Column("review_item_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating IN ('again', 'hard', 'good', 'easy')",
            name=op.f("ck_review_events_rating_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["review_item_id"],
            ["review_items.id"],
            name=op.f("fk_review_events_review_item_id_review_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_events")),
    )
    op.create_index(
        "ix_review_events_item_reviewed_at",
        "review_events",
        ["review_item_id", "reviewed_at"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_index("ix_review_events_item_reviewed_at", table_name="review_events")
    op.drop_table("review_events")
    op.drop_index("uq_review_items_knowledge_id", table_name="review_items")
    op.drop_index("ix_review_items_status_due_at", table_name="review_items")
    op.drop_index("ix_review_items_source_question_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_question_knowledge_knowledge_id", table_name="question_knowledge")
    op.drop_table("question_knowledge")
    op.drop_index("ix_attempt_answers_question_id", table_name="attempt_answers")
    op.drop_table("attempt_answers")
    op.drop_index("ix_ai_explanations_question_id", table_name="ai_explanations")
    op.drop_table("ai_explanations")
    op.drop_index("ix_questions_passage_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_passages_exam_id", table_name="passages")
    op.drop_table("passages")
    op.drop_index("ix_exam_attempts_started_at", table_name="exam_attempts")
    op.drop_index("ix_exam_attempts_exam_id", table_name="exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_index(
        "uq_exams_source_url",
        table_name="exams",
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )
    op.drop_index("ix_exams_status", table_name="exams")
    op.drop_index("ix_exams_source_id", table_name="exams")
    op.drop_index("ix_exams_level_category", table_name="exams")
    op.drop_index("ix_exams_created_at", table_name="exams")
    op.drop_table("exams")
    op.drop_index("uq_sync_changes_entity_version", table_name="sync_changes")
    op.drop_index("ix_sync_changes_changed_at", table_name="sync_changes")
    op.drop_table("sync_changes")
    op.drop_table("knowledge_items")
    op.drop_table("exam_sources")
