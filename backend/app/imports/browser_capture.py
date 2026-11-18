"""Validated, structured capture payload accepted from the local MV3 extension."""

import re
import uuid
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import APIModel, AwareDatetime, HttpUrlStr
from app.database.enums import ExamCategory

_SUPPORTED_PATH = re.compile(r"^/jlpt/N3/\d+/(?:1|3)/?$")


class CapturedQuestion(APIModel):
    number: int | None = Field(default=None, ge=1, le=999)
    section_heading: Annotated[str, StringConstraints(max_length=1000)] = ""
    question_text: Annotated[str, StringConstraints(max_length=5000)] = ""
    options: list[Annotated[str, StringConstraints(max_length=1000)]] = Field(
        default_factory=list, max_length=6
    )
    selected_answer_index: int | None = Field(default=None, ge=0, le=5)
    source_correct_answer_index: int | None = Field(default=None, ge=0, le=5)
    answer_source: Literal["page_result", "page_key"] | None = None
    source_key_conflict: bool = False
    passage: Annotated[str, StringConstraints(max_length=20000)] | None = None
    points: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _indices_fit_options(self) -> Self:
        for name, index in (
            ("selected_answer_index", self.selected_answer_index),
            ("source_correct_answer_index", self.source_correct_answer_index),
        ):
            if index is not None and index >= len(self.options):
                raise ValueError(f"{name} must point to an existing option")
        return self


class BrowserCapture(APIModel):
    schema_version: Literal["1.0"]
    capture_id: uuid.UUID
    source: Literal["dethitiengnhat"]
    source_url: HttpUrlStr
    level: Literal["N3"]
    exam_title: Annotated[str, StringConstraints(max_length=300)] = ""
    category: ExamCategory | None = None
    capture_state: Literal["graded", "ungraded"]
    captured_at: AwareDatetime
    questions: list[CapturedQuestion] = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _supported_source_url(self) -> Self:
        url = urlparse(self.source_url)
        if (
            url.scheme != "https"
            or url.hostname not in {"dethitiengnhat.com", "www.dethitiengnhat.com"}
            or url.username
            or url.password
            or not _SUPPORTED_PATH.fullmatch(url.path)
        ):
            raise ValueError("source_url must be a supported Dethitiengnhat N3 exam page")
        return self
