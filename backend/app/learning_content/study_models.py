"""Web-only study state for imported Android content. Never writes Android Room state."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LearningSourceRight(Base):
    __tablename__ = "learning_source_rights"

    pack_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_content_hash: Mapped[str | None] = mapped_column(Text)
    rights_holder: Mapped[str] = mapped_column(Text, nullable=False)
    rights_basis: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_usage: Mapped[str] = mapped_column(Text, nullable=False)
    attribution: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="private")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearningStudyProgress(Base):
    __tablename__ = "learning_study_progress"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lapse_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_learning_study_progress_due_at", "due_at"),)


class LearningStudyEvent(Base):
    __tablename__ = "learning_study_events"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_study_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rating: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_before_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    was_new: Mapped[bool] = mapped_column(Boolean, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="web")

    __table_args__ = (Index("ix_learning_study_events_item_time", "item_id", "reviewed_at"),)


class LearningSavedItem(Base):
    __tablename__ = "learning_saved_items"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningStudySession(Base):
    __tablename__ = "learning_study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    item_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningExerciseAnswer(Base):
    """Append-only Web answer to a source grammar exercise; never changes SRS."""

    __tablename__ = "learning_exercise_answers"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_content_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    exercise_id: Mapped[str] = mapped_column(Text, nullable=False)
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    exercise_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_learning_exercise_answers_item_time", "item_id", "answered_at"),)
