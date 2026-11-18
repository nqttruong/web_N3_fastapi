"""Validation of AI practice sets (same rules for API and manual JSON).

Errors drop the question (set-level errors reject the whole set). Duplicates are errors:
* exact duplicate of a source/existing question (fingerprint)
* the same stem and option *set* in another order ("reordered_duplicate")
* the same stem as a source question with other options ("same_stem")
Near duplicates (character-trigram similarity ≥ 0.85) are warnings for the user.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.exams.fingerprints import question_fingerprint
from app.knowledge.normalize import clean
from app.practice.context import PracticeContext
from app.practice.payload import PracticeQuestionPayload, PracticeSet

_JA = re.compile(r"[぀-ヿ㐀-鿿]")
NEAR_DUPLICATE = 0.85


@dataclass
class QuestionReport:
    index: int
    question: PracticeQuestionPayload | None
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    fingerprint: str | None = None

    @property
    def ok(self) -> bool:
        return self.question is not None and not self.errors


@dataclass
class SetReport:
    set_errors: list[dict[str, str]]
    questions: list[QuestionReport]

    @property
    def accepted(self) -> list[QuestionReport]:
        return [] if self.set_errors else [q for q in self.questions if q.ok]

    def error_messages(self) -> list[str]:
        msgs = [e["message"] for e in self.set_errors]
        msgs += [f"Câu {q.index + 1}: {e['message']}" for q in self.questions for e in q.errors]
        return msgs


def _trigrams(text: str) -> set[str]:
    t = clean(text)
    return {t[i : i + 3] for i in range(max(0, len(t) - 2))}


def similarity(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_set(raw: dict[str, Any] | PracticeSet, ctx: PracticeContext) -> SetReport:
    try:
        data = raw if isinstance(raw, PracticeSet) else PracticeSet.model_validate(raw)
    except ValidationError as exc:
        return SetReport(
            [
                _err("schema", f"Sai cấu trúc tại {'.'.join(str(p) for p in e['loc'])}: {e['msg']}")
                for e in exc.errors()[:10]
            ],
            [],
        )
    set_errors = []
    if data.knowledge_id != str(ctx.knowledge_id):
        set_errors.append(
            _err("knowledge_id_mismatch", "knowledge_id không khớp mục kiến thức đã chọn.")
        )
    if len(data.questions) > ctx.count:
        set_errors.append(
            _err("too_many", f"Yêu cầu {ctx.count} câu nhưng nhận {len(data.questions)}.")
        )
    if not data.questions:
        set_errors.append(_err("empty", "Không có câu nào."))

    avoid = ctx.avoid_questions
    avoid_fps = {question_fingerprint(a["question_text"], a["options"]) for a in avoid}
    avoid_sets = {
        (clean(a["question_text"]), frozenset(clean(o) for o in a["options"])) for a in avoid
    }
    avoid_stems = {clean(a["question_text"]) for a in avoid}
    seen: set[str] = set()
    reports: list[QuestionReport] = []
    for i, q in enumerate(data.questions):
        r = QuestionReport(i, q)
        n = len(q.options)
        if not 2 <= n <= 6:
            r.errors.append(_err("option_count", "Cần 2–6 lựa chọn."))
        stripped = [clean(o) for o in q.options]
        if any(not s for s in stripped) or len(set(stripped)) != len(stripped):
            r.errors.append(_err("bad_options", "Lựa chọn trống hoặc trùng nhau."))
        if not 0 <= q.answer_index < max(n, 1):
            r.errors.append(_err("answer_out_of_range", "answer_index nằm ngoài các lựa chọn."))
        indices = [o.option_index for o in q.options_analysis]
        if sorted(indices) != list(range(n)):
            r.errors.append(_err("options_analysis", "Phải giải thích đúng mỗi lựa chọn một lần."))
        elif any(
            clean(o.option_text) != clean(q.options[o.option_index]) for o in q.options_analysis
        ):
            r.errors.append(
                _err("option_text_modified", "Phần giải thích chép sai nội dung lựa chọn.")
            )
        if not _JA.search(q.question_text):
            r.errors.append(_err("not_japanese", "Câu hỏi không có tiếng Nhật."))
        if not q.explanation_vi.strip():
            r.errors.append(_err("missing_explanation", "Thiếu giải thích."))
        fp = question_fingerprint(q.question_text, q.options)
        r.fingerprint = fp
        stem = clean(q.question_text)
        if fp in avoid_fps or fp in seen:
            r.errors.append(_err("duplicate", "Trùng hoàn toàn với câu đã có."))
        elif (stem, frozenset(stripped)) in avoid_sets:
            r.errors.append(
                _err(
                    "reordered_duplicate",
                    "Chỉ đổi thứ tự lựa chọn của câu đã có — không phải câu mới.",
                )
            )
        elif stem in avoid_stems:
            r.errors.append(_err("same_stem", "Giữ nguyên câu hỏi gốc, chỉ thay lựa chọn."))
        else:
            best = max(
                (similarity(q.question_text, a["question_text"]) for a in avoid), default=0.0
            )
            if best >= NEAR_DUPLICATE:
                r.warnings.append(
                    _err("near_duplicate", f"Rất giống một câu đã có (độ giống {best:.0%}).")
                )
        if len(q.explanation_vi.strip()) < 20:
            r.warnings.append(_err("thin_explanation", "Giải thích quá ngắn."))
        seen.add(fp)
        reports.append(r)
    return SetReport(set_errors, reports)
