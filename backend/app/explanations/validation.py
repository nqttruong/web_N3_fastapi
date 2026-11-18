"""Two-layer validation of an explanation, identical for API output and manual imports.

Layer 1 — deterministic (errors): schema, question id, verified key, option count/indices/text,
evidence quotes present in the passage. Any error => the explanation is not saved.

Layer 2 — content quality heuristics (warnings): vague or thin reasons, missing distractor
analysis, contradictions with the verified key, missing grammar/vocabulary/kanji items for
the question type, non-kana readings, examples without Japanese, the model's own context /
answer-key concerns. Warnings => status ``needs_review``.

Passing both layers does NOT mean the explanation is linguistically correct; only the user
can approve it.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.database.enums import VerificationStatus
from app.explanations.context import QuestionContext
from app.explanations.payload import SCHEMA_VERSION, ExplanationPayload
from app.imports.textutil import INLINE_TAG_RE

Severity = Literal["error", "warning", "info"]

_WS = re.compile(r"\s+")
_JA = re.compile(r"[぀-ヿ㐀-鿿]")
_KANA_ONLY = re.compile(r"^[぀-ヿー・\s（）()〜~／/、,]+$")
_GENERIC = re.compile(
    r"^(sai|đúng|không (phù hợp|hợp|đúng)( với)?( ngữ cảnh| nghĩa| câu)?|"
    r"không phù hợp ngữ cảnh|sai ngữ pháp|không tự nhiên)[\s.。!]*$",
    re.IGNORECASE,
)
_DECLARED_ANSWER = re.compile(
    r"đáp án(?: đúng)?(?: là)?\s*(?:số\s*)?[（(]?\s*([1-6])\s*[)）]?", re.I
)
MIN_REASON_CHARS = 25


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    option_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "option_index": self.option_index,
        }


@dataclass
class ValidationReport:
    payload: ExplanationPayload | None
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def ok(self) -> bool:
        return self.payload is not None and not self.errors

    def status(self, *, manual: bool) -> VerificationStatus:
        if manual or self.warnings:
            return VerificationStatus.NEEDS_REVIEW
        return VerificationStatus.GENERATED

    def error_messages(self) -> list[str]:
        return [f.message for f in self.errors]


def _norm(text: str) -> str:
    return _WS.sub("", INLINE_TAG_RE.sub("", text))


def parse_payload(
    raw: dict[str, Any] | ExplanationPayload,
) -> tuple[ExplanationPayload | None, list[Finding]]:
    if isinstance(raw, ExplanationPayload):
        return raw, []
    try:
        return ExplanationPayload.model_validate(raw), []
    except ValidationError as exc:
        findings = [
            Finding(
                "error",
                "schema",
                f"Sai cấu trúc tại {'.'.join(str(p) for p in err['loc']) or '(gốc)'}: {err['msg']}",
            )
            for err in exc.errors()[:20]
        ]
        return None, findings


# ----------------------------------------------------------------- layer 1
def deterministic(payload: ExplanationPayload, ctx: QuestionContext) -> list[Finding]:
    out: list[Finding] = []
    n = len(ctx.options)
    if payload.schema_version != SCHEMA_VERSION:
        out.append(Finding("error", "schema_version", f"schema_version phải là {SCHEMA_VERSION}."))
    if payload.question_id != str(ctx.question_id):
        out.append(
            Finding("error", "question_id_mismatch", "question_id không khớp câu được yêu cầu.")
        )
    if payload.correct_answer_index != ctx.correct_index:
        out.append(
            Finding(
                "error",
                "answer_mismatch",
                f"correct_answer_index={payload.correct_answer_index} khác đáp án đã xác nhận "
                f"({ctx.correct_index}). AI không được thay đổi đáp án chuẩn.",
            )
        )
    indices = [o.option_index for o in payload.options_analysis]
    if len(payload.options_analysis) != n:
        out.append(
            Finding(
                "error",
                "option_count",
                f"Cần phân tích đúng {n} lựa chọn, nhận được {len(payload.options_analysis)}.",
            )
        )
    if len(set(indices)) != len(indices):
        out.append(Finding("error", "duplicate_option_index", "option_index bị trùng."))
    missing = sorted(set(range(n)) - set(indices))
    if missing:
        out.append(Finding("error", "missing_option", f"Thiếu phân tích lựa chọn {missing}."))
    extra = sorted(i for i in set(indices) if not 0 <= i < n)
    if extra:
        out.append(Finding("error", "unknown_option", f"option_index không tồn tại: {extra}."))
    correct_flags = [o.option_index for o in payload.options_analysis if o.is_correct]
    if correct_flags != [ctx.correct_index]:
        out.append(
            Finding(
                "error",
                "is_correct_mismatch",
                "Phải có đúng một lựa chọn is_correct=true và trùng đáp án đã xác nhận.",
            )
        )
    for o in payload.options_analysis:
        if 0 <= o.option_index < n and _norm(o.option_text) != _norm(ctx.options[o.option_index]):
            out.append(
                Finding(
                    "error",
                    "option_text_modified",
                    f"Nội dung lựa chọn {o.option_index} bị thay đổi so với đề gốc.",
                    o.option_index,
                )
            )
    if ctx.passage is not None:
        haystack = _norm(ctx.passage)
        for ev in payload.evidence:
            if not ev.quote_ja.strip() or _norm(ev.quote_ja) not in haystack:
                out.append(
                    Finding(
                        "error",
                        "evidence_not_in_passage",
                        f"Trích dẫn không có trong đoạn văn: “{ev.quote_ja[:40]}”.",
                    )
                )
    elif payload.evidence:
        out.append(
            Finding(
                "error", "evidence_without_passage", "Có trích dẫn nhưng câu hỏi không có đoạn văn."
            )
        )
    return out


# ----------------------------------------------------------------- layer 2
def content_quality(payload: ExplanationPayload, ctx: QuestionContext) -> list[Finding]:
    out: list[Finding] = []

    def warn(code: str, message: str, option: int | None = None) -> None:
        out.append(Finding("warning", code, message, option))

    if len(payload.translation_vi.strip()) < 8:
        warn("missing_translation", "Thiếu hoặc quá ngắn phần dịch nghĩa tiếng Việt.")
    if len(payload.correct_explanation.strip()) < MIN_REASON_CHARS:
        warn("thin_correct_explanation", "Giải thích đáp án đúng quá ngắn.")
    for o in payload.options_analysis:
        reason = o.reason.strip()
        if _GENERIC.match(reason):
            warn(
                "generic_reason",
                f"Lý do của lựa chọn {o.option_index} quá chung chung.",
                o.option_index,
            )
        elif len(reason) < MIN_REASON_CHARS:
            warn("thin_reason", f"Lý do của lựa chọn {o.option_index} quá ngắn.", o.option_index)
        if not o.meaning_vi.strip():
            warn("missing_meaning", f"Thiếu nghĩa của lựa chọn {o.option_index}.", o.option_index)
        if not o.is_correct and not (o.difference_from_correct or "").strip():
            warn(
                "missing_difference",
                f"Lựa chọn {o.option_index} thiếu so sánh với đáp án đúng.",
                o.option_index,
            )
        if not o.is_correct and not (o.common_misconception or "").strip():
            warn(
                "missing_misconception",
                f"Lựa chọn {o.option_index} thiếu phân tích vì sao dễ nhầm.",
                o.option_index,
            )
        if o.example_ja and not _JA.search(o.example_ja):
            warn(
                "example_not_japanese",
                f"Ví dụ của lựa chọn {o.option_index} không có tiếng Nhật.",
                o.option_index,
            )

    # Contradiction: the text names a different answer number than the verified one.
    for text in (payload.correct_explanation, payload.solution_summary_vi):
        for m in _DECLARED_ANSWER.finditer(text):
            declared = int(m.group(1))
            if declared not in (ctx.verified_answer, ctx.correct_index):
                warn(
                    "contradiction",
                    f"Lời giải nhắc tới đáp án {declared}, khác đáp án đã xác nhận.",
                )

    if ctx.category == "grammar" and not payload.grammar_points:
        warn("missing_grammar_points", "Câu ngữ pháp nhưng không có mẫu ngữ pháp nào.")
    if ctx.category in {"vocabulary", "kanji"} and not payload.vocabulary:
        warn("missing_vocabulary", "Câu từ vựng/kanji nhưng không có từ vựng nào.")
    if ctx.category == "kanji" and not payload.kanji:
        warn("missing_kanji", "Câu kanji nhưng không có mục kanji nào.")
    if ctx.category == "reading" and ctx.question_type != "text_grammar" and not payload.evidence:
        warn("missing_evidence", "Câu đọc hiểu nhưng không trích dẫn căn cứ từ đoạn văn.")
    for v in payload.vocabulary:
        if v.reading and not _KANA_ONLY.match(v.reading):
            warn("reading_not_kana", f"Cách đọc của “{v.surface}” không phải kana.")
    for g in payload.grammar_points:
        if g.example_ja and not _JA.search(g.example_ja):
            warn("example_not_japanese", f"Ví dụ của mẫu “{g.pattern}” không có tiếng Nhật.")

    if not payload.quality.context_sufficient:
        warn("model_reports_missing_context", "AI báo thiếu ngữ cảnh để giải thích chắc chắn.")
    if payload.quality.source_answer_concern:
        warn(
            "possible_wrong_key",
            "AI nghi ngờ đáp án đã xác nhận có thể sai: "
            f"{payload.quality.source_answer_concern[:300]} "
            "— hãy kiểm tra lại đáp án (không tự đổi).",
        )
    for note in payload.quality.uncertainty_notes[:5]:
        out.append(Finding("info", "uncertainty", note[:300]))
    if ctx.selected_index is None and any(
        "bạn đã chọn" in (o.common_misconception or "").lower() for o in payload.options_analysis
    ):
        warn(
            "invented_learner_answer", "Lời giải nói về lựa chọn của người học dù không có dữ liệu."
        )
    return out


def validate(raw: dict[str, Any] | ExplanationPayload, ctx: QuestionContext) -> ValidationReport:
    payload, findings = parse_payload(raw)
    if payload is None:
        return ValidationReport(None, findings)
    findings = deterministic(payload, ctx)
    if not findings:
        findings += content_quality(payload, ctx)
    return ValidationReport(payload, findings)
