import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.core.schemas import APIModel, AwareDatetime
from app.database.enums import AnswerStatus, AttemptSource, ExamCategory, QuestionType


class AnswerSubmit(APIModel):
    question_id: uuid.UUID
    selected_answer: int | None = Field(
        default=None, ge=1, le=6, description="1-based option index; null = skipped"
    )


class AttemptCreate(APIModel):
    """A completed sitting. Questions of the exam that are not listed count as unanswered."""

    exam_id: uuid.UUID
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = Field(
        default=None, description="Defaults to the server time of submission"
    )
    answers: list[AnswerSubmit] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        ids = [a.question_id for a in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("each question may be answered at most once")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not be before started_at")
        return self


class AttemptSummary(APIModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    exam_category: ExamCategory
    started_at: datetime
    completed_at: datetime | None
    total_questions: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    ungraded_count: int
    source: AttemptSource = Field(
        default=AttemptSource.PRACTICE, description="practice (in app) or import (from a result)"
    )
    accuracy: float | None = Field(
        description="correct / (correct + incorrect); null when nothing could be graded"
    )
    approved_explanation_count: int | None = None
    pending_explanation_count: int | None = None
    created_at: datetime


class AttemptAnswerRead(APIModel):
    question_id: uuid.UUID
    question_number: int
    question_type: QuestionType
    question_text: str
    options: list[str]
    passage_id: uuid.UUID | None
    selected_answer: int | None
    correct_answer: int | None = Field(description="Verified key used for grading at submission")
    is_correct: bool | None
    current_answer_status: AnswerStatus


class AttemptDetail(AttemptSummary):
    exam_source_url: str | None
    answers: list[AttemptAnswerRead]


class MistakeRead(APIModel):
    question_id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    exam_category: ExamCategory
    question_number: int
    question_type: QuestionType
    question_text: str
    options: list[str]
    passage_id: uuid.UUID | None
    occurrences: int
    first_wrong_at: datetime
    last_wrong_at: datetime
    latest_attempt_id: uuid.UUID
    latest_attempt_answer_id: uuid.UUID
    latest_attempt_started_at: datetime
    latest_selected_answer: int
    correct_answer_at_submission: int | None
    current_answer_status: AnswerStatus
    status: Literal["derived"] = "derived"


def accuracy(correct: int, incorrect: int) -> float | None:
    graded = correct + incorrect
    return round(correct / graded, 4) if graded else None
