import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.core.schemas import APIModel, AwareDatetime
from app.database.enums import ReviewItemStatus, ReviewRating, ReviewType, SrsState

Bucket = Literal["due", "upcoming", "completed", "insufficient", "suspended"]


class ReviewItemRead(APIModel):
    id: uuid.UUID
    review_type: ReviewType
    label: str
    knowledge_id: uuid.UUID | None
    related_knowledge_id: uuid.UUID | None
    source_question_id: uuid.UUID | None
    source_question_ids: list[str]
    source_explanation_id: uuid.UUID | None
    status: ReviewItemStatus
    srs_state: SrsState
    step_index: int | None
    interval_minutes: int
    due_at: datetime | None
    last_reviewed_at: datetime | None
    review_count: int
    lapse_count: int
    algorithm_version: str
    ladder: str
    version: int
    blocked_reason: str | None
    created_at: datetime
    updated_at: datetime


class ReviewList(APIModel):
    bucket: Bucket
    counts: dict[str, int]
    items: list[ReviewItemRead]


class SessionCreate(APIModel):
    limit: int = Field(default=20, ge=1, le=50)


class SessionRead(APIModel):
    id: uuid.UUID
    cards: list[dict[str, Any]]
    created_at: datetime
    finished_at: datetime | None


class AnswerRequest(APIModel):
    card_id: str
    selected_index: int | None = Field(
        default=None, ge=0, le=5, description="0-based; null = don't know"
    )


class AnswerResult(APIModel):
    card: dict[str, Any]
    reveal: dict[str, Any]


class EventCreate(APIModel):
    request_id: uuid.UUID = Field(description="Client-generated; re-sending the same id is a no-op")
    review_item_id: uuid.UUID
    rating: ReviewRating
    timezone: str = Field(
        default="UTC", max_length=64, description="IANA zone used for day-based steps"
    )
    session_id: uuid.UUID | None = None
    card_id: str | None = None
    reviewed_at: AwareDatetime | None = None


class EventRead(APIModel):
    id: uuid.UUID
    review_item_id: uuid.UUID
    rating: ReviewRating
    reviewed_at: datetime
    request_id: uuid.UUID | None
    card_kind: str | None
    selected_answer_index: int | None
    answer_correct: bool | None
    previous_state: dict[str, Any] | None
    next_state: dict[str, Any] | None
    next_due_at: datetime | None
    algorithm_version: str | None
    timezone: str | None


class EventResult(APIModel):
    event: EventRead
    duplicate: bool
    item: ReviewItemRead


class HistoryItem(EventRead):
    label: str
    review_type: ReviewType


class StatusUpdate(APIModel):
    version: int = Field(ge=1)
    status: ReviewItemStatus
