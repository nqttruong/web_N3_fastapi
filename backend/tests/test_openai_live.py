"""Opt-in live check against the real OpenAI API (never runs by default / in CI).

    RUN_OPENAI_LIVE=1 OPENAI_API_KEY=sk-... uv run pytest tests/test_openai_live.py -s

Cost control: one self-authored question, output capped at 6000 tokens, no retries.
"""

import os
import uuid

import pytest

from app.core.config import get_settings
from app.explanations.context import QuestionContext
from app.explanations.providers.openai_provider import OpenAIExplanationGenerator
from app.explanations.validation import validate

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OPENAI_LIVE") != "1" or get_settings().openai_api_key is None,
    reason="live OpenAI test is opt-in (RUN_OPENAI_LIVE=1 and OPENAI_API_KEY)",
)


def test_live_grammar_question_is_valid() -> None:
    settings = get_settings().model_copy(update={"ai_max_output_tokens": 6000})
    ctx = QuestionContext(
        question_id=uuid.uuid4(), exam_title="自作", exam_category="grammar", source_url=None,
        question_number=1, question_type="grammar_form", category="grammar",
        question_text="毎日練習した（　　）、試合に勝つことができた。",
        options=["おかげで", "せいで", "くせに", "わりに"], passage=None, verified_answer=1,
        selected_answer=2, content_hash="live",
    )  # fmt: skip
    result = OpenAIExplanationGenerator(settings).generate(ctx)
    report = validate(result.payload, ctx)
    print(
        "model:",
        result.model,
        "usage:",
        result.usage,
        "findings:",
        [f.code for f in report.findings],
    )
    assert report.ok, report.error_messages()
