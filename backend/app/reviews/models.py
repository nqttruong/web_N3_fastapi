"""Review items, review events and review sessions (PR4; tables from PR1 extended).

* A review item is a *task* (re-answer a question, recall a knowledge item, contrast two
  items) — not a copy of a question. ``dedup_key`` makes creation idempotent.
* Scheduling uses the same step-ladder semantics as Android N3 Sensei (app/reviews/srs.py).
  State lives on the item; every answer is an immutable event with before/after state.
* Only events change scheduling: viewing an explanation never counts as a review.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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
from app.database.enums import ReviewItemStatus, ReviewRating, ReviewType, SrsState, check_in


class ReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_items"

    review_type: Mapped[str] = mapped_column(Text, nullable=False)
    # "q:<question_id>", "k:<knowledge_id>", "c:<knowledge_a>:<knowledge_b>" (a < b).
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    knowledge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=True
    )
    related_knowledge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=True
    )
    # Type A: the question to re-answer. Kept from PR1 as source_question_id.
    source_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    source_question_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ReviewItemStatus.ACTIVE.value,
        server_default=ReviewItemStatus.ACTIVE.value,
    )
    # --- scheduling state (Android-compatible) ---
    srs_state: Mapped[str] = mapped_column(
        Text, nullable=False, default=SrsState.NEW.value, server_default="new"
    )
    step_index: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # NULL = new
    interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    lapse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    algorithm_version: Mapped[str] = mapped_column(
        Text, nullable=False, default="ladder-v1", server_default="ladder-v1"
    )
    ladder: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="20m,1h,1d,2d,1w,2w,1mo",
        server_default="20m,1h,1d,2d,1w,2w,1mo",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        CheckConstraint(check_in("status", ReviewItemStatus), name="status_valid"),
        CheckConstraint(check_in("review_type", ReviewType), name="review_type_valid"),
        CheckConstraint(check_in("srs_state", SrsState), name="srs_state_valid"),
        CheckConstraint("jsonb_typeof(source_question_ids) = 'array'", name="sources_is_array"),
        CheckConstraint(
            "review_type <> 'original_question' OR source_question_id IS NOT NULL",
            name="type_a_has_question",
        ),
        CheckConstraint(
            "review_type <> 'knowledge_recall' OR knowledge_id IS NOT NULL",
            name="type_b_has_knowledge",
        ),
        CheckConstraint(
            "review_type <> 'contrast' "
            "OR (knowledge_id IS NOT NULL AND related_knowledge_id IS NOT NULL)",
            name="type_c_has_pair",
        ),
        CheckConstraint(
            "(step_index IS NULL) = (srs_state = 'new')", name="new_items_have_no_step"
        ),
        CheckConstraint(
            "review_count >= 0 AND lapse_count >= 0 AND interval_minutes >= 0",
            name="counters_non_negative",
        ),
        Index("ix_review_items_status_due_at", "status", "due_at"),
        Index("ix_review_items_source_question_id", "source_question_id"),
        Index("ix_review_items_knowledge_id", "knowledge_id"),
    )


class ReviewEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "review_events"

    review_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_items.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Client-generated id (like Android review_records.request_id): replays are ignored.
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, unique=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id", ondelete="SET NULL"), nullable=True
    )
    card_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_answer_index: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )  # 0-based
    answer_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    next_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(check_in("rating", ReviewRating), name="rating_valid"),
        Index("ix_review_events_item_reviewed_at", "review_item_id", "reviewed_at"),
        Index("ix_review_events_reviewed_at", "reviewed_at"),
    )


class ReviewSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Cards of one session, kept server-side so answers are never sent before answering."""

    __tablename__ = "review_sessions"

    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (CheckConstraint("jsonb_typeof(cards) = 'array'", name="cards_is_array"),)
