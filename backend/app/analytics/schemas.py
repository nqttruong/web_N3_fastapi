from pydantic import Field

from app.attempts.schemas import AttemptSummary
from app.core.schemas import APIModel
from app.exams.schemas import ExamRead


class DashboardSummary(APIModel):
    total_exams: int
    total_questions: int
    total_attempts: int
    total_correct: int
    total_incorrect: int
    total_unanswered: int
    total_ungraded: int
    accuracy: float | None = Field(description="correct / (correct + incorrect), all attempts")
    recent_exams: list[ExamRead]
    recent_attempts: list[AttemptSummary]
