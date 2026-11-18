import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.schemas import APIModel
from app.database.enums import (
    ExplanationOrigin,
    JobItemStatus,
    JobStatus,
    VerificationStatus,
)
from app.explanations.payload import ExplanationPayload, LearnerErrorView

MANUAL_JSON_MAX_CHARS = 1_000_000
MAX_EXPORT_QUESTIONS = 20


class FindingRead(BaseModel):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    option_index: int | None = None


class ExplanationRead(APIModel):
    id: uuid.UUID
    question_id: uuid.UUID
    provider: str
    model: str
    origin: ExplanationOrigin
    status: VerificationStatus
    stale: bool = Field(description="Question text/options/passage/verified answer changed since")
    is_current: bool
    prompt_version: str
    schema_version: str
    verified_answer_snapshot: int | None = Field(description="1-based key it was built on")
    flagged_answer_concern: bool
    validation_issues: list[FindingRead]
    payload: ExplanationPayload | None = Field(description="null only for unreadable legacy rows")
    learner_error_analysis: LearnerErrorView | None = None
    usage: dict[str, Any] | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class QuestionExplanations(APIModel):
    question_id: uuid.UUID
    current_id: uuid.UUID | None
    eligible: bool
    ineligible_code: str | None
    ineligible_message: str | None
    versions: list[ExplanationRead]


class GenerateRequest(APIModel):
    question_id: uuid.UUID
    attempt_answer_id: uuid.UUID | None = Field(
        default=None, description="Real attempt answer, used only for the learner-error view"
    )
    force: bool = Field(default=False, description="Regenerate even if a current one exists")


class GenerateResult(APIModel):
    outcome: Literal["cached", "generated"]
    explanation: ExplanationRead


class ReviewRequest(APIModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class BatchRequest(APIModel):
    attempt_id: uuid.UUID
    question_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=500,
        description="Subset of the attempt's questions; default = wrong answers",
    )
    force: bool = False


class JobItemRead(APIModel):
    id: uuid.UUID
    question_id: uuid.UUID
    question_number: int | None
    attempt_answer_id: uuid.UUID | None
    status: JobItemStatus
    tries: int
    error_code: str | None
    error_message: str | None
    explanation_id: uuid.UUID | None


class JobRead(APIModel):
    id: uuid.UUID
    attempt_id: uuid.UUID | None
    status: JobStatus
    force: bool
    counts: dict[str, int]
    items: list[JobItemRead]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class OverviewItem(APIModel):
    attempt_answer_id: uuid.UUID
    question_id: uuid.UUID
    question_number: int
    selected_answer: int | None
    is_correct: bool | None
    eligible: bool
    ineligible_code: str | None
    explanation_id: uuid.UUID | None
    explanation_status: VerificationStatus | None


class AttemptOverview(APIModel):
    attempt_id: uuid.UUID
    wrong_count: int
    eligible_wrong_count: int
    explained_wrong_count: int
    needs_review_count: int
    items: list[OverviewItem]
    latest_job: JobRead | None


class ExportPromptRequest(APIModel):
    question_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_EXPORT_QUESTIONS)
    attempt_id: uuid.UUID | None = None


class SkippedQuestion(APIModel):
    question_id: uuid.UUID
    code: str
    message: str


class ExportPromptResult(APIModel):
    prompt: str
    prompt_version: str
    schema_version: str
    question_ids: list[uuid.UUID]
    skipped: list[SkippedQuestion]
    json_schema: dict[str, Any]


class ManualImportRequest(APIModel):
    question_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=MAX_EXPORT_QUESTIONS,
        description="The questions the prompt was exported for; others are rejected",
    )
    raw_json: Annotated[str, StringConstraints(min_length=1, max_length=MANUAL_JSON_MAX_CHARS)]
    save: bool = Field(default=False, description="false = validate/preview only")
    model_label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = (
        None
    )


class ManualImportItem(APIModel):
    index: int
    question_id: str | None
    ok: bool
    status: VerificationStatus | None
    findings: list[FindingRead]
    payload: ExplanationPayload | None
    saved_explanation_id: uuid.UUID | None = None


class ManualImportResult(APIModel):
    saved: bool
    items: list[ManualImportItem]
    missing_question_ids: list[uuid.UUID]


class Capabilities(APIModel):
    api_available: bool
    provider: str | None
    model: str | None
    reason: str | None
    prompt_version: str
    schema_version: str
    max_concurrent_requests: int
    batch_max_questions: int
    budget: dict[str, Any]
