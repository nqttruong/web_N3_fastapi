"""Read-only imports of licensed Android learning content and their sync audit trail."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LearningSyncQueueLock(Base):
    __tablename__ = "learning_content_sync_queue_lock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class LearningContentPack(Base):
    __tablename__ = "learning_content_packs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    jlpt_level: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_commit_sha: Mapped[str | None] = mapped_column(Text)
    source_manifest_hash: Mapped[str] = mapped_column(Text, nullable=False)
    license_blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LearningLesson(Base):
    __tablename__ = "learning_content_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pack_id: Mapped[str] = mapped_column(
        Text, ForeignKey("learning_content_packs.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("pack_id", "source_id", name="uq_learning_lessons_pack_source"),
        UniqueConstraint("pack_id", "number", name="uq_learning_lessons_pack_number"),
        UniqueConstraint("pack_id", "id", name="uq_learning_lessons_pack_id_id"),
        CheckConstraint("number > 0 AND order_index >= 0", name="lesson_order_valid"),
        Index("ix_learning_lessons_pack_order", "pack_id", "order_index"),
    )


class LearningExample(Base):
    __tablename__ = "learning_content_examples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pack_id: Mapped[str] = mapped_column(
        Text, ForeignKey("learning_content_packs.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("pack_id", "source_ref", name="uq_learning_examples_pack_source"),
        UniqueConstraint("pack_id", "id", name="uq_learning_examples_pack_id_id"),
        Index("ix_learning_examples_pack", "pack_id"),
    )


class LearningItem(Base):
    __tablename__ = "learning_content_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pack_id: Mapped[str] = mapped_column(
        Text, ForeignKey("learning_content_packs.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    jlpt_level: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_license: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("pack_id", "item_type", "source_ref", name="uq_learning_items_source"),
        UniqueConstraint("pack_id", "id", name="uq_learning_items_pack_id_id"),
        ForeignKeyConstraint(
            ["pack_id", "lesson_id"],
            ["learning_content_lessons.pack_id", "learning_content_lessons.id"],
            ondelete="RESTRICT",
            name="fk_learning_items_pack_lesson",
        ),
        CheckConstraint(
            "item_type IN ('vocabulary', 'kanji', 'grammar')", name="learning_item_type_valid"
        ),
        CheckConstraint("order_index >= 0", name="learning_item_order_valid"),
        Index("ix_learning_items_type_level", "item_type", "jlpt_level", "is_archived"),
        Index("ix_learning_items_lesson_order", "lesson_id", "order_index"),
    )


class LearningItemExample(Base):
    __tablename__ = "learning_content_item_examples"

    pack_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    example_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("order_index >= 0", name="learning_example_order_valid"),
        ForeignKeyConstraint(
            ["pack_id", "item_id"],
            ["learning_content_items.pack_id", "learning_content_items.id"],
            ondelete="RESTRICT",
            name="fk_learning_item_examples_pack_item",
        ),
        ForeignKeyConstraint(
            ["pack_id", "example_id"],
            ["learning_content_examples.pack_id", "learning_content_examples.id"],
            ondelete="RESTRICT",
            name="fk_learning_item_examples_pack_example",
        ),
    )


class LearningSyncRun(Base):
    __tablename__ = "learning_content_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    source_commit_sha: Mapped[str | None] = mapped_column(Text)
    source_manifest_hash: Mapped[str | None] = mapped_column(Text)
    counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'no_changes', 'failed')",
            name="learning_sync_status_valid",
        ),
        CheckConstraint(
            "trigger IN ('startup', 'interval', 'manual')", name="learning_sync_trigger_valid"
        ),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="learning_sync_attempts_valid"),
        Index("ix_learning_sync_runs_requested", "status", "requested_at"),
    )


class LearningContentChange(Base):
    __tablename__ = "learning_content_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_content_sync_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pack_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_hash: Mapped[str | None] = mapped_column(Text)
    new_hash: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[int | None] = mapped_column(Integer)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('pack', 'lesson', 'example', 'vocabulary', 'kanji', 'grammar')",
            name="learning_change_entity_valid",
        ),
        CheckConstraint(
            "change_type IN ('created', 'updated', 'archived', 'restored')",
            name="learning_change_type_valid",
        ),
        ForeignKeyConstraint(
            ["pack_id"],
            ["learning_content_packs.id"],
            ondelete="RESTRICT",
            name="fk_learning_changes_pack",
        ),
        Index("ix_learning_changes_run", "run_id", "changed_at"),
        Index("ix_learning_changes_source", "pack_id", "entity_type", "source_ref"),
    )
