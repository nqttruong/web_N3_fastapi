"""Practice-set schema v1.0 (Structured Outputs compatible: no constraints, all fields
required, nullable where optional). Indices are 0-based."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

PRACTICE_SCHEMA_VERSION = "1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PracticeOption(_Strict):
    option_index: int
    option_text: str
    reason: str  # why it is right / wrong


class PracticeQuestionPayload(_Strict):
    question_type: str
    question_text: str
    options: list[str]
    answer_index: int  # proposed by the AI — becomes usable only after user approval
    explanation_vi: str
    options_analysis: list[PracticeOption]
    focus: str  # which aspect of the knowledge item it trains


class PracticeSet(_Strict):
    schema_version: Literal["1.0"]
    knowledge_id: str
    questions: list[PracticeQuestionPayload]
