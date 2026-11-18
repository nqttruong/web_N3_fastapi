"""Knowledge items (grammar / vocabulary / kanji words / reading skills), their links to
questions, relations between items and provenance (PR4; tables created schema-only in PR1).

Official items are only created from *approved, non-stale* explanations after the user
confirms a preview. Statistics are computed from attempt answers of linked questions —
an AI hypothesis never lowers proficiency by itself.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import (
    JlptLevel,
    KnowledgeLink,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    check_in,
)


class KnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_items"

    knowledge_type: Mapped[str] = mapped_column(Text, nullable=False)
    jlpt_level: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)  # display label, e.g. "〜ので"
    content: Mapped[str] = mapped_column(Text, nullable=False)  # short Vietnamese summary
    # Type-specific dedup key (see app/knowledge/normalize.py). A "#n" suffix marks a
    # separate sense created deliberately by the user (homographs, same form/other function).
    canonical_key: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=KnowledgeStatus.ACTIVE.value, server_default="active"
    )
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="SET NULL"), nullable=True
    )
    # Explanation the item was first extracted from (provenance; more in knowledge_evidence).
    source_explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )
    # Future link to Android content ids, e.g. "GRAMMAR:g_node" (never generated on the web).
    android_ref: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        CheckConstraint(check_in("knowledge_type", KnowledgeType), name="knowledge_type_valid"),
        CheckConstraint(check_in("jlpt_level", JlptLevel), name="jlpt_level_valid"),
        CheckConstraint(check_in("status", KnowledgeStatus), name="status_valid"),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(btrim(canonical_key)) > 0", name="canonical_key_not_blank"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_is_object"),
        CheckConstraint(
            "(status = 'merged') = (merged_into_id IS NOT NULL)", name="merged_has_target"
        ),
        # One live item per key; merged/archived items keep their key for history.
        Index(
            "uq_knowledge_items_type_key_active",
            "knowledge_type",
            "canonical_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_knowledge_items_type_status", "knowledge_type", "status"),
    )


class QuestionKnowledge(CreatedAtMixin, Base):
    __tablename__ = "question_knowledge"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(check_in("relation_type", KnowledgeRelation), name="relation_type_valid"),
        Index("ix_question_knowledge_knowledge_id", "knowledge_id"),
    )


class KnowledgeRelationLink(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_relations"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(check_in("relation_type", KnowledgeLink), name="relation_type_valid"),
        CheckConstraint("source_id <> target_id", name="no_self_relation"),
        CheckConstraint(
            "relation_type = 'prerequisite' OR source_id < target_id",
            name="symmetric_relations_ordered",
        ),
        UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_knowledge_relations_pair"
        ),
        Index("ix_knowledge_relations_target_id", "target_id"),
    )


class KnowledgeEvidence(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Why an item exists: which question + approved explanation it was confirmed from,
    with a snapshot of the extracted fields at confirmation time."""

    __tablename__ = "knowledge_evidence"

    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True
    )
    explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_explanations.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(check_in("role", KnowledgeRelation), name="role_valid"),
        UniqueConstraint(
            "knowledge_id", "question_id", "explanation_id", name="uq_knowledge_evidence_source"
        ),
        Index("ix_knowledge_evidence_question_id", "question_id"),
    )
