"""AI-generated practice questions (PR4). Never official until the user approves one."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import (
    ExplanationOrigin,
    PracticeGenerationStatus,
    PracticeStatus,
    check_in,
)


class PracticeGeneration(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One generation request (API call or manual import), processed synchronously."""

    __tablename__ = "practice_generations"

    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    requested_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    accepted_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(check_in("origin", ExplanationOrigin), name="origin_valid"),
        CheckConstraint(check_in("status", PracticeGenerationStatus), name="status_valid"),
        CheckConstraint("requested_count BETWEEN 1 AND 10", name="requested_count_range"),
        CheckConstraint(
            "accepted_count >= 0 AND accepted_count <= requested_count",
            name="accepted_le_requested",
        ),
        Index("ix_practice_generations_knowledge_id", "knowledge_id"),
    )


class GeneratedPracticeQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generated_practice_questions"

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    source_explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=PracticeStatus.NEEDS_REVIEW.value,
        server_default="needs_review",
    )
    question_type: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    answer_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0-based, AI-proposed
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # incl. explanations
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    validation_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        CheckConstraint(check_in("status", PracticeStatus), name="status_valid"),
        CheckConstraint(
            "jsonb_typeof(options) = 'array' AND jsonb_array_length(options) BETWEEN 2 AND 6",
            name="options_array",
        ),
        CheckConstraint(
            "answer_index >= 0 AND answer_index < jsonb_array_length(options)",
            name="answer_in_range",
        ),
        CheckConstraint(
            "status = 'needs_review' OR reviewed_at IS NOT NULL", name="review_has_timestamp"
        ),
        Index("ix_generated_practice_knowledge_status", "knowledge_id", "status"),
        Index("ix_generated_practice_fingerprint", "fingerprint"),
    )
