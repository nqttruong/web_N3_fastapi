"""Exam attempts: one row per submitted sitting, one answer row per question."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.database.enums import AttemptSource, check_in


class ExamAttempt(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "exam_attempts"

    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unanswered_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Answered, but the question had no *verified* key at submission time.
    ungraded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=AttemptSource.PRACTICE.value,
        server_default=AttemptSource.PRACTICE.value,
    )
    # Set when the attempt was reconstructed from an import; UNIQUE => one attempt per draft
    # (idempotent commit).
    import_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_drafts.id", ondelete="SET NULL"), nullable=True
    )

    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptAnswer.question_number",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name="fk_exam_attempts_exam_id_exams", ondelete="RESTRICT"
        ),
        UniqueConstraint("id", "exam_id", name="uq_exam_attempts_id_exam_id"),
        CheckConstraint(
            "correct_count >= 0 AND incorrect_count >= 0 AND unanswered_count >= 0 "
            "AND ungraded_count >= 0",
            name="counts_non_negative",
        ),
        CheckConstraint(
            "correct_count + incorrect_count + unanswered_count + ungraded_count = total_questions",
            name="counts_sum_to_total",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="completed_after_started"
        ),
        CheckConstraint(check_in("source", AttemptSource), name="source_valid"),
        CheckConstraint(
            # draft link may be cleared (SET NULL) when the draft is deleted; history stays.
            "import_draft_id IS NULL OR source = 'import'",
            name="import_draft_only_for_imports",
        ),
        Index(
            "uq_exam_attempts_import_draft_id",
            "import_draft_id",
            unique=True,
            postgresql_where=text("import_draft_id IS NOT NULL"),
        ),
        Index("ix_exam_attempts_exam_id", "exam_id"),
        Index("ix_exam_attempts_started_at", "started_at"),
    )


class AttemptAnswer(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "attempt_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Denormalised exam_id lets composite FKs prove the question belongs to the attempt's exam.
    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Snapshot so history stays readable even if the question is renumbered later.
    question_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    selected_answer: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Verified key used for grading at submission time (NULL = no verified key).
    correct_answer_snapshot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # NULL when unanswered or when no verified key existed.
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    attempt: Mapped[ExamAttempt] = relationship(back_populates="answers")

    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "exam_id"],
            ["exam_attempts.id", "exam_attempts.exam_id"],
            name="fk_attempt_answers_attempt_same_exam",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["exam_id", "question_id"],
            ["questions.exam_id", "questions.id"],
            name="fk_attempt_answers_question_same_exam",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answers_attempt_question"),
        CheckConstraint(
            "selected_answer IS NULL OR selected_answer >= 1", name="selected_answer_positive"
        ),
        CheckConstraint(
            "(is_correct IS NULL) = (selected_answer IS NULL OR correct_answer_snapshot IS NULL)",
            name="is_correct_consistent",
        ),
        CheckConstraint(
            "is_correct IS NULL OR is_correct = (selected_answer = correct_answer_snapshot)",
            name="is_correct_matches_snapshot",
        ),
        Index("ix_attempt_answers_question_id", "question_id"),
    )
