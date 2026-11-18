"""AI explanations (PR3): versioned explanations, batch jobs, API usage log.

Additive: extends ai_explanations (from PR1, schema-only until now) and adds three tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10 22:16:31.714673
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')", name=op.f("ck_ai_requests_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_ai_requests_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_requests")),
    )
    op.create_index("ix_ai_requests_created_at", "ai_requests", ["created_at"], unique=False)
    op.create_table(
        "explanation_jobs",
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("force", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'running', 'completed', 'partial_failed', 'failed', 'cancelled')",
            name=op.f("ck_explanation_jobs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exam_attempts.id"],
            name=op.f("fk_explanation_jobs_attempt_id_exam_attempts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_explanation_jobs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_explanation_jobs_idempotency_key")),
    )
    op.create_index(
        "ix_explanation_jobs_attempt_id", "explanation_jobs", ["attempt_id"], unique=False
    )
    op.create_index("ix_explanation_jobs_status", "explanation_jobs", ["status"], unique=False)
    op.create_table(
        "explanation_job_items",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("attempt_answer_id", sa.UUID(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("tries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("explanation_id", sa.UUID(), nullable=True),
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
            "status IN ('pending', 'running', 'cached', 'succeeded', 'failed', 'skipped', 'cancelled')",
            name=op.f("ck_explanation_job_items_status_valid"),
        ),
        sa.CheckConstraint("tries >= 0", name=op.f("ck_explanation_job_items_tries_non_negative")),
        sa.ForeignKeyConstraint(
            ["attempt_answer_id"],
            ["attempt_answers.id"],
            name=op.f("fk_explanation_job_items_attempt_answer_id_attempt_answers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["explanation_id"],
            ["ai_explanations.id"],
            name=op.f("fk_explanation_job_items_explanation_id_ai_explanations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["explanation_jobs.id"],
            name=op.f("fk_explanation_job_items_job_id_explanation_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_explanation_job_items_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_explanation_job_items")),
        sa.UniqueConstraint("job_id", "question_id", name="uq_explanation_job_items_job_question"),
    )
    op.create_index(
        "ix_explanation_job_items_question_id",
        "explanation_job_items",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "ix_explanation_job_items_status",
        "explanation_job_items",
        ["status", "lease_expires_at"],
        unique=False,
    )
    op.add_column(
        "ai_explanations", sa.Column("origin", sa.Text(), server_default="api", nullable=False)
    )
    op.add_column(
        "ai_explanations",
        sa.Column("prompt_version", sa.Text(), server_default="legacy", nullable=False),
    )
    op.add_column(
        "ai_explanations",
        sa.Column("schema_version", sa.Text(), server_default="legacy", nullable=False),
    )
    op.add_column(
        "ai_explanations",
        sa.Column("content_hash", sa.Text(), server_default="legacy", nullable=False),
    )
    op.add_column(
        "ai_explanations",
        sa.Column("cache_key", sa.Text(), server_default="legacy", nullable=False),
    )
    op.add_column(
        "ai_explanations", sa.Column("verified_answer_snapshot", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "ai_explanations",
        sa.Column(
            "validation_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "ai_explanations",
        sa.Column(
            "flagged_answer_concern", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "ai_explanations",
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ai_explanations", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("ai_explanations", sa.Column("review_note", sa.Text(), nullable=True))
    # Rows from before PR3 (schema-only in PR1, normally none) keep the 'legacy' markers: their
    # content_hash never matches a current question, so they are shown as stale, never current.
    for col in ("prompt_version", "schema_version", "content_hash", "cache_key"):
        op.alter_column("ai_explanations", col, server_default=None)

    # Review states: unverified/verified/rejected (PR1) -> generated/needs_review/approved/rejected
    op.drop_constraint(
        op.f("ck_ai_explanations_verification_status_valid"), "ai_explanations", type_="check"
    )
    op.execute(
        "UPDATE ai_explanations SET verification_status = 'needs_review' WHERE verification_status = 'unverified'"
    )
    op.execute(
        "UPDATE ai_explanations SET verification_status = 'approved', reviewed_at = updated_at WHERE verification_status = 'verified'"
    )
    op.execute(
        "UPDATE ai_explanations SET reviewed_at = updated_at WHERE verification_status = 'rejected'"
    )
    op.alter_column("ai_explanations", "verification_status", server_default="needs_review")
    op.create_check_constraint(
        op.f("ck_ai_explanations_verification_status_valid"),
        "ai_explanations",
        "verification_status IN ('generated', 'needs_review', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        op.f("ck_ai_explanations_origin_valid"), "ai_explanations", "origin IN ('api', 'manual')"
    )
    op.create_check_constraint(
        op.f("ck_ai_explanations_issues_is_array"),
        "ai_explanations",
        "jsonb_typeof(validation_issues) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_ai_explanations_review_has_timestamp"),
        "ai_explanations",
        "verification_status NOT IN ('approved', 'rejected') OR reviewed_at IS NOT NULL",
    )
    op.create_index("ix_ai_explanations_cache_key", "ai_explanations", ["cache_key"], unique=False)
    op.create_index(
        "ix_ai_explanations_question_content",
        "ai_explanations",
        ["question_id", "content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_ai_explanations_review_has_timestamp"), "ai_explanations", type_="check"
    )
    op.drop_constraint(op.f("ck_ai_explanations_issues_is_array"), "ai_explanations", type_="check")
    op.drop_constraint(op.f("ck_ai_explanations_origin_valid"), "ai_explanations", type_="check")
    op.drop_constraint(
        op.f("ck_ai_explanations_verification_status_valid"), "ai_explanations", type_="check"
    )
    op.execute(
        "UPDATE ai_explanations SET verification_status = 'unverified' WHERE verification_status IN ('generated', 'needs_review')"
    )
    op.execute(
        "UPDATE ai_explanations SET verification_status = 'verified' WHERE verification_status = 'approved'"
    )
    op.alter_column("ai_explanations", "verification_status", server_default="unverified")
    op.create_check_constraint(
        op.f("ck_ai_explanations_verification_status_valid"),
        "ai_explanations",
        "verification_status IN ('unverified', 'verified', 'rejected')",
    )
    op.drop_index("ix_ai_explanations_question_content", table_name="ai_explanations")
    op.drop_index("ix_ai_explanations_cache_key", table_name="ai_explanations")
    op.drop_column("ai_explanations", "review_note")
    op.drop_column("ai_explanations", "reviewed_at")
    op.drop_column("ai_explanations", "usage")
    op.drop_column("ai_explanations", "flagged_answer_concern")
    op.drop_column("ai_explanations", "validation_issues")
    op.drop_column("ai_explanations", "verified_answer_snapshot")
    op.drop_column("ai_explanations", "cache_key")
    op.drop_column("ai_explanations", "content_hash")
    op.drop_column("ai_explanations", "schema_version")
    op.drop_column("ai_explanations", "prompt_version")
    op.drop_column("ai_explanations", "origin")
    op.drop_index("ix_explanation_job_items_status", table_name="explanation_job_items")
    op.drop_index("ix_explanation_job_items_question_id", table_name="explanation_job_items")
    op.drop_table("explanation_job_items")
    op.drop_index("ix_explanation_jobs_status", table_name="explanation_jobs")
    op.drop_index("ix_explanation_jobs_attempt_id", table_name="explanation_jobs")
    op.drop_table("explanation_jobs")
    op.drop_index("ix_ai_requests_created_at", table_name="ai_requests")
    op.drop_table("ai_requests")
