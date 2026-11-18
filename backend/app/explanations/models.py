"""AI explanations (PR3): versioned explanations, batch jobs and an API usage log.

An explanation may *flag* a doubtful answer key, but it never changes
``questions.correct_answer``/``answer_status``. Approval is always a user action.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import (
    AIRequestStatus,
    ExplanationOrigin,
    JobItemStatus,
    JobStatus,
    VerificationStatus,
    check_in,
)


class AIExplanation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_explanations"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    # Validated payload (see app/explanations/payload.py), indices 0-based.
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # generated | needs_review | approved | rejected (column name kept from PR1).
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=VerificationStatus.NEEDS_REVIEW.value,
        server_default=VerificationStatus.NEEDS_REVIEW.value,
    )
    origin: Mapped[str] = mapped_column(
        Text, nullable=False, default=ExplanationOrigin.API.value, server_default="api"
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    # Hash of question text, options, passage, type and verified answer at generation time.
    # A different current hash => the explanation is stale.
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # content_hash + provider + model + prompt_version + schema_version.
    cache_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Verified key (1-based, DB convention) the explanation was built on.
    verified_answer_snapshot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Deterministic + content-quality issues found when the explanation was saved.
    validation_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # Set when the model reported that the source answer key may be wrong.
    flagged_answer_concern: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            check_in("verification_status", VerificationStatus), name="verification_status_valid"
        ),
        CheckConstraint(check_in("origin", ExplanationOrigin), name="origin_valid"),
        CheckConstraint("jsonb_typeof(explanation_json) = 'object'", name="explanation_is_object"),
        CheckConstraint("jsonb_typeof(validation_issues) = 'array'", name="issues_is_array"),
        CheckConstraint(
            "length(btrim(provider)) > 0 AND length(btrim(model)) > 0", name="provider_model_set"
        ),
        CheckConstraint(
            "verification_status NOT IN ('approved', 'rejected') OR reviewed_at IS NOT NULL",
            name="review_has_timestamp",
        ),
        Index("ix_ai_explanations_question_id", "question_id"),
        Index("ix_ai_explanations_question_content", "question_id", "content_hash"),
        Index("ix_ai_explanations_cache_key", "cache_key"),
    )


class ExplanationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Batch of explanation requests, persisted so progress survives reloads/restarts."""

    __tablename__ = "explanation_jobs"

    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default=JobStatus.PENDING.value)
    force: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["ExplanationJobItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="ExplanationJobItem.position"
    )

    __table_args__ = (
        CheckConstraint(check_in("status", JobStatus), name="status_valid"),
        Index("ix_explanation_jobs_attempt_id", "attempt_id"),
        Index("ix_explanation_jobs_status", "status"),
    )


class ExplanationJobItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "explanation_job_items"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("explanation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attempt_answers.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=JobItemStatus.PENDING.value)
    tries: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Worker lease: a running item whose lease expired is recovered after a restart.
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )

    job: Mapped[ExplanationJob] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint(check_in("status", JobItemStatus), name="status_valid"),
        CheckConstraint("tries >= 0", name="tries_non_negative"),
        UniqueConstraint("job_id", "question_id", name="uq_explanation_job_items_job_question"),
        Index("ix_explanation_job_items_status", "status", "lease_expires_at"),
        Index("ix_explanation_job_items_question_id", "question_id"),
    )


class AIRequest(Base):
    """One row per provider call (success or failure). No prompt/response content is stored."""

    __tablename__ = "ai_requests"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(check_in("status", AIRequestStatus), name="status_valid"),
        Index("ix_ai_requests_created_at", "created_at"),
    )
