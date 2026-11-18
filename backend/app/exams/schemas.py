import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import APIModel, HttpUrlStr, NonBlankStr
from app.database.enums import (
    AnswerSource,
    AnswerStatus,
    ExamCategory,
    ExamStatus,
    JlptLevel,
    QuestionType,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]
OptionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
PassageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
]


# ---------- Exam sources ----------
class ExamSourceCreate(APIModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    base_url: HttpUrlStr


class ExamSourceRead(APIModel):
    id: uuid.UUID
    name: str
    base_url: str
    created_at: datetime


# ---------- Exams ----------
class ExamCreate(APIModel):
    title: Title
    level: JlptLevel = JlptLevel.N3
    category: ExamCategory
    description: Description | None = None
    source_url: HttpUrlStr | None = None
    source_id: uuid.UUID | None = None
    status: ExamStatus = ExamStatus.DRAFT


class ExamUpdate(APIModel):
    """Partial update. Omitted fields are untouched; nullable fields accept ``null``."""

    title: Title | None = None
    level: JlptLevel | None = None
    category: ExamCategory | None = None
    description: Description | None = None
    source_url: HttpUrlStr | None = None
    source_id: uuid.UUID | None = None
    status: ExamStatus | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> Self:
        for name in ("title", "level", "category", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ExamRead(APIModel):
    id: uuid.UUID
    source_id: uuid.UUID | None
    source_name: str | None
    source_url: str | None
    level: JlptLevel
    category: ExamCategory
    title: str
    description: str | None
    status: ExamStatus
    question_count: int
    verified_answer_count: int
    attempt_count: int | None = None
    latest_attempt_started_at: datetime | None = None
    latest_attempt_accuracy: float | None = None
    approved_explanation_count: int | None = None
    created_at: datetime
    updated_at: datetime


# ---------- Passages ----------
class PassageCreate(APIModel):
    content: PassageText


class PassageRead(APIModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    content: str
    created_at: datetime


# ---------- Questions ----------
class _QuestionAnswerRules(APIModel):
    @staticmethod
    def check_answer(
        options: list[str] | None,
        correct_answer: int | None,
        answer_status: AnswerStatus | None,
    ) -> None:
        if options is not None:
            normalised = [o.strip() for o in options]
            if len(set(normalised)) != len(normalised):
                raise ValueError("options must be unique")
            if correct_answer is not None and correct_answer > len(options):
                raise ValueError(f"correct_answer must be between 1 and {len(options)}")
        if correct_answer is None and answer_status not in (None, AnswerStatus.MISSING):
            raise ValueError("answer_status requires correct_answer")
        if correct_answer is not None and answer_status == AnswerStatus.MISSING:
            raise ValueError("answer_status 'missing' cannot be used with a correct_answer")


class QuestionCreate(_QuestionAnswerRules):
    question_number: int = Field(ge=1, le=999)
    question_type: QuestionType
    question_text: QuestionText
    options: list[OptionText] = Field(min_length=2, max_length=6)
    correct_answer: int | None = Field(default=None, ge=1, le=6, description="1-based option")
    answer_status: AnswerStatus | None = Field(
        default=None,
        description=(
            "Trust level of correct_answer. Defaults to 'unverified' when an answer is given "
            "and 'missing' otherwise. Only 'verified' answers are used for grading."
        ),
    )
    passage_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_answer(self) -> Self:
        self.check_answer(self.options, self.correct_answer, self.answer_status)
        if self.answer_status is None:
            self.answer_status = (
                AnswerStatus.MISSING if self.correct_answer is None else AnswerStatus.UNVERIFIED
            )
        return self


class QuestionUpdate(_QuestionAnswerRules):
    question_number: int | None = Field(default=None, ge=1, le=999)
    question_type: QuestionType | None = None
    question_text: QuestionText | None = None
    options: list[OptionText] | None = Field(default=None, min_length=2, max_length=6)
    correct_answer: int | None = Field(default=None, ge=1, le=6)
    answer_status: AnswerStatus | None = None
    passage_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for name in ("question_number", "question_type", "question_text", "options"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        # Cross-field checks against the stored row happen in the service.
        if "options" in self.model_fields_set and self.options is not None:
            normalised = [o.strip() for o in self.options]
            if len(set(normalised)) != len(normalised):
                raise ValueError("options must be unique")
        return self


class QuestionRead(APIModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    passage_id: uuid.UUID | None
    question_number: int
    question_type: QuestionType
    question_text: str
    options: list[str]
    correct_answer: int | None = Field(
        description="Stored answer key (null when hidden via include_answers=false)."
    )
    answer_status: AnswerStatus
    answer_source: AnswerSource | None = Field(
        default=None, description="Provenance of correct_answer (null when hidden or absent)."
    )
    created_at: datetime
    updated_at: datetime


class ExamListFilters(APIModel):
    q: NonBlankStr | None = None
    category: ExamCategory | None = None
    status: ExamStatus | None = None
    level: JlptLevel | None = None
