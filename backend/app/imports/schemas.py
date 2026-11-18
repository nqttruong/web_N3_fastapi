"""Pydantic models for import drafts.

``DraftContent`` is what the parser produces, what the user edits in the preview, and what is
stored in ``import_drafts.content``. Three answers are kept apart on purpose:

* ``site_answer``    — the answer the *source* showed (HTML key, 正解 marker, OCR). A hint.
* ``user_answer``    — what the user picked when they took the test on the site.
* ``correct_answer`` — the answer the user designates as the key. Only becomes ``verified``
  on commit when ``answer_confirmed`` is true, which only the user can set.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import APIModel, AwareDatetime, HttpUrlStr
from app.database.enums import (
    AnswerSource,
    ExamCategory,
    ImportMethod,
    ImportStatus,
    JlptLevel,
    OcrStatus,
    QuestionType,
)

MAX_QUESTIONS = 300
MAX_PASSAGES = 100
Key = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,40}$")]
AnswerIndex = Annotated[int, Field(ge=1, le=6)]


class ParserNote(APIModel):
    code: str
    message: str


# ------------------------------------------------------------------ issues
Severity = Literal["error", "warning", "info"]


class Issue(APIModel):
    severity: Severity
    code: str
    message: str
    question_key: str | None = None
    data: dict[str, Any] | None = None


class DraftExam(APIModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""
    category: ExamCategory | None = None
    level: JlptLevel = JlptLevel.N3
    description: Annotated[str, StringConstraints(max_length=5000)] | None = None


class DraftPassage(APIModel):
    key: Key
    content: Annotated[str, StringConstraints(max_length=20000)]


class DraftQuestion(APIModel):
    key: Key
    include: bool = Field(default=True, description="false = skip on commit (e.g. 例 examples)")
    question_number: int | None = Field(default=None, ge=1, le=999)
    question_type: QuestionType = QuestionType.OTHER
    question_text: Annotated[str, StringConstraints(max_length=5000)] = ""
    options: list[Annotated[str, StringConstraints(max_length=1000)]] = Field(
        default_factory=list, max_length=6
    )
    passage_key: Key | None = None
    site_answer: AnswerIndex | None = None
    user_answer: AnswerIndex | None = None
    correct_answer: AnswerIndex | None = None
    # Derived by the server from correct_answer/site_answer; client values are ignored.
    answer_source: AnswerSource | None = None
    answer_confirmed: bool = False
    # Parser uncertainty. A question with notes must be marked reviewed before commit.
    parser_notes: list[ParserNote] = Field(default_factory=list)
    reviewed: bool = False
    points: float | None = None
    is_example: bool = False

    @model_validator(mode="after")
    def _confirmation_needs_answer(self) -> Self:
        if self.answer_confirmed and self.correct_answer is None:
            raise ValueError("answer_confirmed requires correct_answer")
        return self


class DraftAttempt(APIModel):
    """Optional attempt reconstructed from ``user_answer`` values. Times must be supplied by
    the user; the server never invents them."""

    create: bool = False
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None


class DraftContent(APIModel):
    exam: DraftExam = Field(default_factory=DraftExam)
    passages: list[DraftPassage] = Field(default_factory=list, max_length=MAX_PASSAGES)
    questions: list[DraftQuestion] = Field(default_factory=list, max_length=MAX_QUESTIONS)
    attempt: DraftAttempt = Field(default_factory=DraftAttempt)
    # Draft-level notes from the adapter (read-only for clients; kept across edits).
    parse_notes: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> Self:
        qkeys = [q.key for q in self.questions]
        pkeys = [p.key for p in self.passages]
        if len(set(qkeys)) != len(qkeys):
            raise ValueError("question keys must be unique")
        if len(set(pkeys)) != len(pkeys):
            raise ValueError("passage keys must be unique")
        return self


class DraftSummary(APIModel):
    total_questions: int
    included_questions: int
    valid_questions: int
    missing_answer: int
    needs_review: int
    confirmed_answers: int
    with_user_answer: int
    errors: int
    warnings: int


# ------------------------------------------------------------------ requests
class _CreateBase(APIModel):
    source_url: HttpUrlStr | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    category: ExamCategory | None = None


class TextImportCreate(_CreateBase):
    text: Annotated[str, StringConstraints(min_length=1)]


class HtmlImportCreate(_CreateBase):
    html: Annotated[str, StringConstraints(min_length=1)]


class DraftUpdate(APIModel):
    version: int = Field(ge=1, description="Must equal the stored version (optimistic locking)")
    content: DraftContent | None = None
    source_url: HttpUrlStr | None = None
    asset_order: list[uuid.UUID] | None = Field(
        default=None, description="New order of image assets (all asset ids)."
    )

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not ({"content", "source_url", "asset_order"} & self.model_fields_set):
            raise ValueError("at least one of content, source_url, asset_order is required")
        return self


class ReparseRequest(APIModel):
    raw_input: Annotated[str, StringConstraints(min_length=1)] | None = Field(
        default=None, description="Replace the stored text/HTML before parsing (text/html only)."
    )


class CommitRequest(APIModel):
    target: Literal["new", "existing"] = "new"
    existing_exam_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _target(self) -> Self:
        if (self.target == "existing") != (self.existing_exam_id is not None):
            raise ValueError("existing_exam_id is required exactly when target is 'existing'")
        return self


# ------------------------------------------------------------------ responses
class AssetRead(APIModel):
    id: uuid.UUID
    position: int
    original_filename: str | None
    detected_type: str
    byte_size: int
    width: int
    height: int
    ocr_status: OcrStatus
    ocr_engine: str | None
    ocr_text: str | None


class DraftListItem(APIModel):
    id: uuid.UUID
    status: ImportStatus
    method: ImportMethod
    adapter: str | None
    source_url: str | None
    title: str
    question_count: int
    issues: list[Issue] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    exam_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DraftRead(APIModel):
    id: uuid.UUID
    status: ImportStatus
    method: ImportMethod
    adapter: str | None
    source_url: str | None
    raw_input: str | None
    content: DraftContent
    issues: list[Issue]
    summary: DraftSummary
    assets: list[AssetRead]
    error_code: str | None
    error_message: str | None
    version: int
    exam_id: uuid.UUID | None
    attempt_id: uuid.UUID | None
    committed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CommitResult(APIModel):
    draft_id: uuid.UUID
    exam_id: uuid.UUID
    attempt_id: uuid.UUID | None
    already_committed: bool
    created_questions: int
    reused_questions: int
    upgraded_answers: int
    warnings: list[Issue]


class OcrCapability(APIModel):
    available: bool
    engine: str | None
    languages: list[str]
    reason: str | None


class ImportLimits(APIModel):
    max_text_chars: int
    max_html_bytes: int
    max_images: int
    max_image_bytes: int
    max_image_pixels: int
    accepted_image_types: list[str]


class ImportCapabilities(APIModel):
    ocr: OcrCapability
    limits: ImportLimits
    adapters: list[str]
