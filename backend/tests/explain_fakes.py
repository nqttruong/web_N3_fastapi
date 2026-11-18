"""Fake explanation provider for tests — never calls a real API."""

import copy
from collections.abc import Callable
from typing import Any

from app.explanations.context import QuestionContext
from app.explanations.interfaces import GenerationResult, ProviderError, Usage
from app.explanations.payload import ExplanationPayload


def good_payload(ctx: QuestionContext) -> dict[str, Any]:
    options = []
    for i, text in enumerate(ctx.options):
        correct = i == ctx.correct_index
        options.append(
            {
                "option_index": i,
                "option_text": text,
                "meaning_vi": f"Nghĩa của lựa chọn {i + 1}: {text}",
                "is_correct": correct,
                "reason": (
                    f"「{text}」 khớp với cấu trúc và ý nghĩa của câu nên là đáp án đúng."
                    if correct
                    else f"「{text}」 mang nghĩa khác, không nối được với vế sau của câu này."
                ),
                "when_it_would_be_correct": None
                if correct
                else f"Dùng 「{text}」 khi câu nói về tình huống khác.",
                "difference_from_correct": None
                if correct
                else "Khác đáp án đúng về sắc thái và cách kết nối.",
                "common_misconception": None
                if correct
                else "Người học có thể nhầm vì hai từ có âm gần giống nhau.",
                "how_to_distinguish": None
                if correct
                else "Chú ý từ đứng sau chỗ trống để chọn mẫu phù hợp.",
                "example_ja": f"{text}を使った例文です。",
                "example_vi": "Câu ví dụ.",
            }
        )
    evidence = []
    if ctx.passage:
        evidence = [
            {
                "quote_ja": ctx.passage.split("。")[0],
                "explanation_vi": "Câu đầu đoạn văn nêu ý chính.",
            }
        ]
    return {
        "schema_version": "1.0",
        "question_id": str(ctx.question_id),
        "correct_answer_index": ctx.correct_index,
        "translation_vi": "Bản dịch tiếng Việt của câu hỏi.",
        "solution_summary_vi": f"Đáp án đúng là lựa chọn {ctx.verified_answer}.",
        "correct_explanation": "Lựa chọn này đúng vì ngữ pháp và nghĩa đều phù hợp với câu.",
        "recognition_tips": "Nhìn từ đứng sau chỗ trống.",
        "options_analysis": options,
        "grammar_points": [
            {
                "pattern": "〜ので",
                "meaning_vi": "vì",
                "usage": "Nêu nguyên nhân khách quan.",
                "contrast": "〜のに: trái với mong đợi",
                "example_ja": "雨なので、出かけません。",
            }
        ],
        "vocabulary": [
            {"surface": "試合", "reading": "しあい", "meaning_vi": "trận đấu", "note": None}
        ],
        "kanji": [{"kanji": "試", "readings": "音: シ", "meaning_vi": "thử", "note": None}],
        "sentence_structure": None,
        "evidence": evidence,
        "key_takeaway": "Phân biệt nguyên nhân (ので) và trái ngược (のに).",
        "review_topics": ["〜ので", "〜のに"],
        "quality": {
            "context_sufficient": True,
            "source_answer_concern": None,
            "uncertainty_notes": [],
        },
    }


Step = ProviderError | Callable[[dict[str, Any]], dict[str, Any]] | None


class FakeGenerator:
    """Each call consumes one step: an exception to raise, a mutator applied to a good
    payload, or None (= good payload). After the steps run out, good payloads are returned."""

    provider = "fake"
    model = "fake-model-1"

    def __init__(self, steps: list[Step] | None = None, fail_for: set[str] | None = None) -> None:
        self.steps = list(steps or [])
        self.fail_for = fail_for or set()
        self.calls: list[tuple[QuestionContext, list[str] | None]] = []

    def generate(
        self, ctx: QuestionContext, *, feedback: list[str] | None = None
    ) -> GenerationResult:
        self.calls.append((ctx, feedback))
        if str(ctx.question_id) in self.fail_for:
            from app.explanations.interfaces import ProviderBadRequestError

            raise ProviderBadRequestError("forced failure")
        step = self.steps.pop(0) if self.steps else None
        if isinstance(step, ProviderError):
            raise step
        data = good_payload(ctx)
        if callable(step):
            data = step(copy.deepcopy(data))
        payload = ExplanationPayload.model_validate(data)
        return GenerationResult(payload=payload, usage=Usage(1200, 900), model=self.model)
