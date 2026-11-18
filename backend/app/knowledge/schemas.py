import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import APIModel
from app.database.enums import (
    KnowledgeLink,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    ReviewItemStatus,
    ReviewType,
    SrsState,
    VerificationStatus,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Summary = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Priority = Literal["review_now", "due_soon", "stable", "insufficient_data"]


# ------------------------------------------------------------------ extraction preview
class ExtractRequest(APIModel):
    question_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    attempt_id: uuid.UUID | None = Field(
        default=None, description="Use the attempt's wrong answers"
    )

    @model_validator(mode="after")
    def _one(self) -> "ExtractRequest":
        if (self.question_ids is None) == (self.attempt_id is None):
            raise ValueError("provide exactly one of question_ids or attempt_id")
        return self


class MatchRead(APIModel):
    knowledge_id: uuid.UUID
    title: str
    content: str
    reason: Literal["same_key", "similar_title"]
    meaning_similarity: float


class CandidateRead(APIModel):
    ref: str
    question_id: uuid.UUID
    explanation_id: uuid.UUID
    knowledge_type: KnowledgeType
    canonical_key: str
    title: str
    summary: str
    details: dict[str, Any]
    role: KnowledgeRelation
    selected: bool
    action: Literal["create", "link", "needs_decision"]
    match: MatchRead | None
    warnings: list[str]


class RelationCandidateRead(APIModel):
    source_ref: str
    target_ref: str
    relation_type: Literal["confused_with"]


class QuestionExtractionRead(APIModel):
    question_id: uuid.UUID
    question_number: int
    explanation_id: uuid.UUID | None
    skipped_code: str | None
    skipped_message: str | None
    candidates: list[CandidateRead]
    relations: list[RelationCandidateRead]


class ExtractResult(APIModel):
    questions: list[QuestionExtractionRead]
    reading_skills: dict[str, str]


# ------------------------------------------------------------------ confirm
class ConfirmItem(APIModel):
    ref: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    question_id: uuid.UUID
    explanation_id: uuid.UUID
    knowledge_type: KnowledgeType
    title: Title
    summary: Summary = ""
    details: dict[str, Any] = Field(default_factory=dict)
    role: KnowledgeRelation
    action: Literal["create", "link", "create_new_sense", "skip"]
    target_knowledge_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _target(self) -> "ConfirmItem":
        if (self.action == "link") != (self.target_knowledge_id is not None):
            raise ValueError("target_knowledge_id is required exactly when action is 'link'")
        return self


class ConfirmRelation(APIModel):
    source_ref: str
    target_ref: str
    relation_type: KnowledgeLink = KnowledgeLink.CONFUSED_WITH


class ConfirmRequest(APIModel):
    items: list[ConfirmItem] = Field(min_length=1, max_length=300)
    relations: list[ConfirmRelation] = Field(default_factory=list, max_length=300)
    create_reviews: bool = True


class ConfirmedItem(APIModel):
    ref: str
    knowledge_id: uuid.UUID | None
    outcome: Literal["created", "linked", "skipped"]


class ConfirmResult(APIModel):
    items: list[ConfirmedItem]
    created: int
    linked: int
    skipped: int
    relations_created: int
    review_items_created: int
    review_items_existing: int


# ------------------------------------------------------------------ read
class KnowledgeStats(APIModel):
    encounters: int
    correct: int
    incorrect: int
    unanswered: int
    ungraded: int
    never_attempted_questions: int
    error_rate: float | None
    error_rate_low: float | None
    error_rate_high: float | None
    confidence: Literal["none", "low", "medium", "high"]
    recent_incorrect_7d: int
    last_incorrect_at: datetime | None
    review_events: int
    last_rating: str | None
    next_due_at: datetime | None
    priority: Priority


class KnowledgeListItem(APIModel):
    id: uuid.UUID
    knowledge_type: KnowledgeType
    title: str
    content: str
    canonical_key: str
    status: KnowledgeStatus
    question_count: int
    stats: KnowledgeStats
    created_at: datetime
    updated_at: datetime


class LinkedQuestion(APIModel):
    question_id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    question_number: int
    question_text: str
    role: KnowledgeRelation
    mistakes: list[dict[str, Any]]


class RelatedItem(APIModel):
    knowledge_id: uuid.UUID
    title: str
    knowledge_type: KnowledgeType
    relation_type: KnowledgeLink
    direction: Literal["outgoing", "incoming", "symmetric"]


class EvidenceRead(APIModel):
    question_id: uuid.UUID | None
    explanation_id: uuid.UUID | None
    explanation_status: VerificationStatus | None
    explanation_stale: bool | None
    role: KnowledgeRelation
    extracted: dict[str, Any]
    confirmed_at: datetime


class ReviewItemBrief(APIModel):
    id: uuid.UUID
    review_type: ReviewType
    status: ReviewItemStatus
    srs_state: SrsState
    due_at: datetime | None
    review_count: int
    last_reviewed_at: datetime | None


class KnowledgeDetail(KnowledgeListItem):
    details: dict[str, Any]
    merged_into_id: uuid.UUID | None
    source_explanation_id: uuid.UUID | None
    version: int
    questions: list[LinkedQuestion]
    related: list[RelatedItem]
    evidence: list[EvidenceRead]
    review_items: list[ReviewItemBrief]


class KnowledgeUpdate(APIModel):
    version: int = Field(ge=1)
    title: Title | None = None
    content: Summary | None = None
    details: dict[str, Any] | None = None
    status: Literal["active", "archived"] | None = None


class MergeRequest(APIModel):
    target_id: uuid.UUID
    source_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class SplitRequest(APIModel):
    title: Title
    content: Summary = ""
    question_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class RelationCreate(APIModel):
    target_id: uuid.UUID
    relation_type: KnowledgeLink
