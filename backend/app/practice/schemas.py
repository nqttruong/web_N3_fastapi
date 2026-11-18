import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import Field, StringConstraints

from app.core.schemas import APIModel
from app.database.enums import ExplanationOrigin, PracticeGenerationStatus, PracticeStatus


class GenerateRequest(APIModel):
    knowledge_id: uuid.UUID
    count: int = Field(default=3, ge=1, le=5)
    question_type: Annotated[str, StringConstraints(max_length=40)] | None = None


class ExportRequest(GenerateRequest):
    pass


class ManualImportRequest(APIModel):
    knowledge_id: uuid.UUID
    count: int = Field(default=5, ge=1, le=5)
    raw_json: Annotated[str, StringConstraints(min_length=1, max_length=500_000)]
    save: bool = False
    model_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = (
        None
    )


class ReviewRequest(APIModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class PracticeQuestionRead(APIModel):
    id: uuid.UUID
    generation_id: uuid.UUID
    knowledge_id: uuid.UUID
    source_explanation_id: uuid.UUID | None
    status: PracticeStatus
    question_type: str
    question_text: str
    options: list[str]
    answer_index: int
    payload: dict[str, Any]
    validation_issues: list[dict[str, Any]]
    reviewed_at: datetime | None
    review_note: str | None
    times_used: int
    created_at: datetime


class GenerationRead(APIModel):
    id: uuid.UUID
    knowledge_id: uuid.UUID
    origin: ExplanationOrigin
    provider: str
    model: str
    prompt_version: str
    requested_count: int
    accepted_count: int
    status: PracticeGenerationStatus
    issues: list[dict[str, Any]]
    usage: dict[str, Any] | None
    created_at: datetime
    questions: list[PracticeQuestionRead]


class PreviewQuestion(APIModel):
    index: int
    ok: bool
    errors: list[dict[str, str]]
    warnings: list[dict[str, str]]
    question: dict[str, Any] | None


class ManualImportResult(APIModel):
    saved: bool
    set_errors: list[dict[str, str]]
    questions: list[PreviewQuestion]
    generation: GenerationRead | None


class ExportResult(APIModel):
    prompt: str
    prompt_version: str
    json_schema: dict[str, Any]
