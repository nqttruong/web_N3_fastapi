"""Exam content: sources, exams, passages and questions (the "original exam" side)."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import (
    AnswerSource,
    AnswerStatus,
    ExamCategory,
    ExamStatus,
    JlptLevel,
    QuestionType,
    check_in,
)


class ExamSource(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "exam_sources"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("base_url ~* '^https?://'", name="base_url_http"),
    )


class Exam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exams"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_sources.id", ondelete="SET NULL"), nullable=True
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(Text, nullable=False, default=JlptLevel.N3.value)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=ExamStatus.DRAFT.value, server_default=ExamStatus.DRAFT.value
    )

    source: Mapped[ExamSource | None] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint(check_in("level", JlptLevel), name="level_valid"),
        CheckConstraint(check_in("category", ExamCategory), name="category_valid"),
        CheckConstraint(check_in("status", ExamStatus), name="status_valid"),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        CheckConstraint("source_url IS NULL OR source_url ~* '^https?://'", name="source_url_http"),
        # The same source page must not be imported twice. Manual exams have no URL.
        Index(
            "uq_exams_source_url",
            "source_url",
            unique=True,
            postgresql_where=text("source_url IS NOT NULL"),
        ),
        Index("ix_exams_level_category", "level", "category"),
        Index("ix_exams_status", "status"),
        Index("ix_exams_created_at", "created_at"),
        Index("ix_exams_source_id", "source_id"),
    )


class Passage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "passages"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("length(btrim(content)) > 0", name="content_not_blank"),
        # (exam_id, id) is unique so questions can reference a passage *of the same exam*.
        UniqueConstraint("exam_id", "id", name="uq_passages_exam_id_id"),
        Index("ix_passages_exam_id", "exam_id"),
    )


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    passage_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    question_type: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Ordered list of option strings, e.g. ["あける", "ひらける", ...]. Answers are 1-based.
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    answer_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=AnswerStatus.MISSING.value,
        server_default=AnswerStatus.MISSING.value,
    )
    # Provenance of correct_answer (PR2). NULL exactly when there is no answer.
    answer_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sha256 of normalised (passage_id, text, options) — blocks the same question twice per exam.
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of normalised (text, options) without the passage — finds the same question in
    # *other* exams (duplicate detection only, never used to merge automatically).
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["exam_id", "passage_id"],
            ["passages.exam_id", "passages.id"],
            name="fk_questions_passage_same_exam",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("exam_id", "question_number", name="uq_questions_exam_id_question_number"),
        UniqueConstraint("exam_id", "content_hash", name="uq_questions_exam_id_content_hash"),
        UniqueConstraint("exam_id", "id", name="uq_questions_exam_id_id"),
        CheckConstraint("question_number > 0", name="question_number_positive"),
        CheckConstraint(check_in("question_type", QuestionType), name="question_type_valid"),
        CheckConstraint(check_in("answer_status", AnswerStatus), name="answer_status_valid"),
        CheckConstraint("length(btrim(question_text)) > 0", name="question_text_not_blank"),
        CheckConstraint(
            "jsonb_typeof(options) = 'array' AND jsonb_array_length(options) BETWEEN 2 AND 6",
            name="options_array_2_to_6",
        ),
        CheckConstraint(
            "correct_answer IS NULL OR "
            "(correct_answer >= 1 AND correct_answer <= jsonb_array_length(options))",
            name="correct_answer_in_range",
        ),
        CheckConstraint(
            "(answer_status = 'missing') = (correct_answer IS NULL)",
            name="answer_status_matches_answer",
        ),
        CheckConstraint(check_in("answer_source", AnswerSource), name="answer_source_valid"),
        CheckConstraint(
            "(answer_source IS NULL) = (correct_answer IS NULL)",
            name="answer_source_matches_answer",
        ),
        Index("ix_questions_passage_id", "passage_id"),
        Index("ix_questions_fingerprint", "fingerprint"),
    )

    @property
    def verified_answer(self) -> int | None:
        return self.correct_answer if self.answer_status == AnswerStatus.VERIFIED else None
