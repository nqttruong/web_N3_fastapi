"""Explanation payload: the Structured Outputs schema the model must fill, version 1.0.

Rules for OpenAI strict mode (checked against the docs on 2026-11-10): every field required,
optional values expressed as ``T | None``, ``additionalProperties: false``, no ``minLength``.
So this model carries *no* constraints; all rules live in ``validation.py`` and are
enforced identically for API output and for JSON pasted back from ChatGPT.

Indices are **0-based** (Android convention). The database stores answers 1-based.

The payload is the *general* explanation of a question. It contains no personal data: the
per-learner view ("why you probably chose this") is derived from the analysis of the option
the learner actually selected — see ``learner_error_view``.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OptionAnalysis(_Strict):
    option_index: int
    option_text: str  # must reproduce the original option exactly (checked)
    meaning_vi: str
    is_correct: bool
    reason: str  # concrete reason why it is right / wrong in THIS sentence
    when_it_would_be_correct: str | None  # wrong options: a context where it would fit
    difference_from_correct: str | None  # wrong options: contrast with the key
    common_misconception: str | None  # wrong options: why a learner may pick it
    how_to_distinguish: str | None  # wrong options: memory / distinction tip
    example_ja: str | None
    example_vi: str | None


class GrammarPoint(_Strict):
    pattern: str
    meaning_vi: str
    usage: str
    contrast: str | None
    example_ja: str | None


class VocabularyItem(_Strict):
    surface: str
    reading: str  # kana
    meaning_vi: str
    note: str | None


class KanjiItem(_Strict):
    kanji: str
    readings: str  # e.g. "音: セイ / 訓: ととの(える)"
    meaning_vi: str
    note: str | None


class Evidence(_Strict):
    quote_ja: str  # must appear verbatim in the passage (checked)
    explanation_vi: str


class ModelQuality(_Strict):
    context_sufficient: bool
    # Non-null when the model believes the verified key may be wrong. Never changes the key.
    source_answer_concern: str | None
    uncertainty_notes: list[str]


class ExplanationPayload(_Strict):
    schema_version: Literal["1.0"]
    question_id: str
    correct_answer_index: int
    translation_vi: str
    solution_summary_vi: str
    correct_explanation: str
    recognition_tips: str | None
    options_analysis: list[OptionAnalysis]
    grammar_points: list[GrammarPoint]
    vocabulary: list[VocabularyItem]
    kanji: list[KanjiItem]
    sentence_structure: str | None
    evidence: list[Evidence]
    key_takeaway: str
    review_topics: list[str]
    quality: ModelQuality


class LearnerErrorView(BaseModel):
    """Derived per attempt answer; only produced when a real selection exists."""

    selected_answer_index: int
    is_correct: bool
    selected_option_text: str
    possible_misconception: str | None
    how_to_distinguish: str | None
    study_advice: str


def learner_error_view(
    payload: ExplanationPayload, selected_index: int | None
) -> LearnerErrorView | None:
    if selected_index is None:
        return None
    option = next((o for o in payload.options_analysis if o.option_index == selected_index), None)
    if option is None:
        return None
    advice = payload.key_takeaway
    if payload.review_topics:
        advice = f"{advice} Ôn lại: {', '.join(payload.review_topics)}."
    return LearnerErrorView(
        selected_answer_index=selected_index,
        is_correct=option.is_correct,
        selected_option_text=option.option_text,
        possible_misconception=None if option.is_correct else option.common_misconception,
        how_to_distinguish=None if option.is_correct else option.how_to_distinguish,
        study_advice=advice,
    )


def output_json_schema() -> dict[str, object]:
    """JSON schema shown to ChatGPT in manual mode (same model as the API path)."""
    return ExplanationPayload.model_json_schema()


Category = Literal["vocabulary", "kanji", "grammar", "reading"]
