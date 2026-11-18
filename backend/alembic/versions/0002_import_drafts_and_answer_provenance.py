"""Import drafts, image assets, answer provenance and attempt source (PR2).

Additive only: no PR1 table or column is dropped; existing rows are backfilled.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10 20:57:18.893602
"""

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Frozen copy of the fingerprint normalisation at the time of this migration. Migrations must
# not import application code that may change later.
_WS = re.compile(r"\s+")


def _norm(value: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def _fingerprint(question_text: str, options: list[str]) -> str:
    payload = json.dumps(
        {"t": _norm(question_text), "o": [_norm(o) for o in options]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _backfill_questions() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, question_text, options FROM questions")).all()
    for row in rows:
        conn.execute(
            sa.text("UPDATE questions SET fingerprint = :fp WHERE id = :id"),
            {"fp": _fingerprint(row.question_text, list(row.options)), "id": row.id},
        )
    # Every answer that existed before PR2 was entered through the manual form.
    conn.execute(
        sa.text("UPDATE questions SET answer_source = 'manual' WHERE correct_answer IS NOT NULL")
    )


def upgrade() -> None:
    op.create_table(
        "import_drafts",
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("adapter", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column("raw_sha256", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
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
            "(method = 'images') = (raw_input IS NULL)",
            name=op.f("ck_import_drafts_raw_input_matches_method"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(content) = 'object'", name=op.f("ck_import_drafts_content_is_object")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(issues) = 'array'", name=op.f("ck_import_drafts_issues_is_array")
        ),
        sa.CheckConstraint(
            "method IN ('text', 'html', 'images')", name=op.f("ck_import_drafts_method_valid")
        ),
        sa.CheckConstraint(
            "source_url IS NULL OR source_url ~* '^https?://'",
            name=op.f("ck_import_drafts_source_url_http"),
        ),
        sa.CheckConstraint(
            "status <> 'committed' OR committed_at IS NOT NULL",
            name=op.f("ck_import_drafts_committed_has_timestamp"),
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'parsing', 'needs_review', 'ready', 'committed', 'failed')",
            name=op.f("ck_import_drafts_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name=op.f("fk_import_drafts_exam_id_exams"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_drafts")),
    )
    op.create_index("ix_import_drafts_created_at", "import_drafts", ["created_at"], unique=False)
    op.create_index("ix_import_drafts_exam_id", "import_drafts", ["exam_id"], unique=False)
    op.create_index("ix_import_drafts_raw_sha256", "import_drafts", ["raw_sha256"], unique=False)
    op.create_index("ix_import_drafts_source_url", "import_drafts", ["source_url"], unique=False)
    op.create_index("ix_import_drafts_status", "import_drafts", ["status"], unique=False)
    op.create_table(
        "import_assets",
        sa.Column("draft_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("detected_type", sa.Text(), nullable=False),
        sa.Column("stored_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("ocr_status", sa.Text(), nullable=False),
        sa.Column("ocr_engine", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "detected_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name=op.f("ck_import_assets_detected_type_valid"),
        ),
        sa.CheckConstraint(
            "ocr_status IN ('pending', 'done', 'failed')",
            name=op.f("ck_import_assets_ocr_status_valid"),
        ),
        sa.CheckConstraint(
            "storage_path !~ '(^/|\\.\\.)'", name=op.f("ck_import_assets_storage_path_relative")
        ),
        sa.CheckConstraint(
            "stored_type = 'image/png'", name=op.f("ck_import_assets_stored_type_png")
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name=op.f("ck_import_assets_dimensions_positive"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_import_assets_position_non_negative")),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["import_drafts.id"],
            name=op.f("fk_import_assets_draft_id_import_drafts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_assets")),
        sa.UniqueConstraint(
            "draft_id",
            "position",
            deferrable=True,
            initially="DEFERRED",
            name="uq_import_assets_draft_position",
        ),
        sa.UniqueConstraint("storage_path", name=op.f("uq_import_assets_storage_path")),
    )
    # --- exam_attempts: provenance of the attempt -------------------------------------
    op.add_column(
        "exam_attempts", sa.Column("source", sa.Text(), server_default="practice", nullable=False)
    )
    op.add_column("exam_attempts", sa.Column("import_draft_id", sa.UUID(), nullable=True))
    op.create_index(
        "uq_exam_attempts_import_draft_id",
        "exam_attempts",
        ["import_draft_id"],
        unique=True,
        postgresql_where=sa.text("import_draft_id IS NOT NULL"),
    )
    op.create_foreign_key(
        op.f("fk_exam_attempts_import_draft_id_import_drafts"),
        "exam_attempts",
        "import_drafts",
        ["import_draft_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_exam_attempts_source_valid"), "exam_attempts", "source IN ('practice', 'import')"
    )
    op.create_check_constraint(
        op.f("ck_exam_attempts_import_draft_only_for_imports"),
        "exam_attempts",
        "import_draft_id IS NULL OR source = 'import'",
    )

    # --- questions: answer provenance + cross-exam fingerprint -------------------------
    op.add_column("questions", sa.Column("answer_source", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("fingerprint", sa.Text(), nullable=True))
    _backfill_questions()
    op.alter_column("questions", "fingerprint", nullable=False)
    op.create_index("ix_questions_fingerprint", "questions", ["fingerprint"], unique=False)
    op.create_check_constraint(
        op.f("ck_questions_answer_source_valid"),
        "questions",
        "answer_source IN ('manual', 'site_key', 'user_entered', 'ocr')",
    )
    op.create_check_constraint(
        op.f("ck_questions_answer_source_matches_answer"),
        "questions",
        "(answer_source IS NULL) = (correct_answer IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_questions_answer_source_matches_answer"), "questions", type_="check"
    )
    op.drop_constraint(op.f("ck_questions_answer_source_valid"), "questions", type_="check")
    op.drop_constraint(
        op.f("ck_exam_attempts_import_draft_only_for_imports"), "exam_attempts", type_="check"
    )
    op.drop_constraint(op.f("ck_exam_attempts_source_valid"), "exam_attempts", type_="check")
    op.drop_index("ix_questions_fingerprint", table_name="questions")
    op.drop_column("questions", "fingerprint")
    op.drop_column("questions", "answer_source")
    op.drop_constraint(
        op.f("fk_exam_attempts_import_draft_id_import_drafts"), "exam_attempts", type_="foreignkey"
    )
    op.drop_index(
        "uq_exam_attempts_import_draft_id",
        table_name="exam_attempts",
        postgresql_where=sa.text("import_draft_id IS NOT NULL"),
    )
    op.drop_column("exam_attempts", "import_draft_id")
    op.drop_column("exam_attempts", "source")
    op.drop_table("import_assets")
    op.drop_index("ix_import_drafts_status", table_name="import_drafts")
    op.drop_index("ix_import_drafts_source_url", table_name="import_drafts")
    op.drop_index("ix_import_drafts_raw_sha256", table_name="import_drafts")
    op.drop_index("ix_import_drafts_exam_id", table_name="import_drafts")
    op.drop_index("ix_import_drafts_created_at", table_name="import_drafts")
    op.drop_table("import_drafts")
