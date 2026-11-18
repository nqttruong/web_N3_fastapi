"""Append-only change log for future device sync (schema only in PR1).

``id`` is a monotonically increasing BIGINT so clients can pull "changes after cursor N".
Nothing writes to this table yet; see docs/android-integration-plan.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.enums import SyncOperation, check_in

SYNCABLE_ENTITY_TYPES = (
    "exam",
    "passage",
    "question",
    "exam_attempt",
    "attempt_answer",
    "knowledge_item",
    "question_knowledge",
    "review_item",
    "review_event",
    "ai_explanation",
    "android_review_event",
)


class SyncCursorLock(Base):
    """Singleton row used to serialize cursor allocation until the transaction commits."""

    __tablename__ = "sync_cursor_lock"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)


class SyncChange(Base):
    __tablename__ = "sync_changes"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, server_default=func.next_sync_cursor()
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="1.0")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(check_in("operation", SyncOperation), name="operation_valid"),
        CheckConstraint(
            "entity_type IN (" + ", ".join(f"'{t}'" for t in SYNCABLE_ENTITY_TYPES) + ")",
            name="entity_type_valid",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("uq_sync_changes_entity_version", "entity_type", "entity_id", "version", unique=True),
        Index("ix_sync_changes_changed_at", "changed_at"),
    )


class AndroidReviewEvent(Base):
    """Immutable Android event inbox; the server never imports client SRS state."""

    __tablename__ = "android_review_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_devices.id", ondelete="RESTRICT"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_before_minutes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interval_after_minutes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_at_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("item_type IN ('VOCABULARY', 'KANJI', 'GRAMMAR')", name="item_type_valid"),
        CheckConstraint("rating IN ('AGAIN', 'HARD', 'GOOD', 'EASY')", name="rating_valid"),
        CheckConstraint(
            "interval_before_minutes >= 0 AND interval_after_minutes >= 0",
            name="interval_non_negative",
        ),
        Index("ix_android_review_events_item_time", "item_type", "item_id", "reviewed_at"),
    )
