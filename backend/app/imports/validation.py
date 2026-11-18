"""Structural validation of a draft (no database access) and summary counts."""

from datetime import datetime

from app.attempts.service import CLOCK_SKEW
from app.core.time import utcnow
from app.database.enums import AnswerSource, ImportMethod
from app.exams.fingerprints import normalise_for_hash
from app.imports.schemas import DraftContent, DraftSummary, Issue, Severity


def derive_answer_sources(content: DraftContent, method: ImportMethod) -> None:
    """Server-side provenance; the client never sets it."""
    site_source = AnswerSource.OCR if method == ImportMethod.IMAGES else AnswerSource.SITE_KEY
    for q in content.questions:
        if q.correct_answer is None:
            q.answer_source = None
            q.answer_confirmed = False
        elif q.site_answer is not None and q.correct_answer == q.site_answer:
            q.answer_source = site_source
        else:
            q.answer_source = AnswerSource.USER_ENTERED


def structural_issues(content: DraftContent) -> list[Issue]:
    issues: list[Issue] = []
    exam = content.exam
    if not exam.title.strip():
        issues.append(Issue(severity="error", code="missing_title", message="Chưa có tên đề."))
    if exam.category is None:
        issues.append(
            Issue(severity="error", code="missing_category", message="Chưa chọn loại đề.")
        )

    included = [q for q in content.questions if q.include]
    if not included:
        issues.append(
            Issue(severity="error", code="no_questions", message="Không có câu hỏi nào để lưu.")
        )
    passage_keys = {p.key for p in content.passages}
    seen_numbers: dict[int, str] = {}
    seen_content: dict[tuple[str | None, str], str] = {}

    for q in included:

        def add(severity: Severity, code: str, message: str, key: str = q.key) -> None:
            issues.append(Issue(severity=severity, code=code, message=message, question_key=key))

        label = f"Câu {q.question_number}" if q.question_number else "Câu chưa đánh số"
        n_opts = len(q.options)
        if not q.question_text.strip():
            add("error", "empty_text", f"{label}: thiếu nội dung câu hỏi.")
        if n_opts < 2:
            add("error", "too_few_options", f"{label}: cần ít nhất 2 lựa chọn.")
        elif n_opts != 4:
            add("warning", "option_count", f"{label}: có {n_opts} lựa chọn (JLPT thường có 4).")
        if any(not o.strip() for o in q.options):
            add("error", "empty_option", f"{label}: có lựa chọn bị trống.")
        stripped = [o.strip() for o in q.options]
        if len(set(stripped)) != len(stripped):
            add("error", "duplicate_options", f"{label}: các lựa chọn bị trùng.")
        for field, value in (
            ("correct_answer", q.correct_answer),
            ("site_answer", q.site_answer),
            ("user_answer", q.user_answer),
        ):
            if value is not None and value > n_opts:
                add(
                    "error",
                    "answer_out_of_range",
                    f"{label}: {field} = {value} vượt quá số lựa chọn.",
                )
        if q.question_number is None:
            add("error", "missing_number", f"{label}: thiếu số câu.")
        elif q.question_number in seen_numbers:
            add("error", "duplicate_number", f"Số câu {q.question_number} bị trùng trong bản nháp.")
        else:
            seen_numbers[q.question_number] = q.key
        if q.passage_key is not None and q.passage_key not in passage_keys:
            add("error", "unknown_passage", f"{label}: đoạn văn liên kết không tồn tại.")
        fp = (
            q.passage_key,
            normalise_for_hash(q.question_text)
            + "\x1f"
            + "\x1f".join(map(normalise_for_hash, q.options)),
        )
        if q.question_text.strip() and fp in seen_content:
            add(
                "error",
                "duplicate_content",
                f"{label}: trùng nội dung với một câu khác trong bản nháp.",
            )
        else:
            seen_content[fp] = q.key
        unreviewed = [n for n in q.parser_notes if not q.reviewed]
        if unreviewed:
            add(
                "error",
                "needs_review",
                f"{label}: cần kiểm tra ({'; '.join(n.message for n in unreviewed[:3])}).",
            )
        if q.correct_answer is None:
            add(
                "warning",
                "missing_answer",
                f"{label}: chưa có đáp án — sẽ lưu là “chưa có đáp án”.",
            )
        elif not q.answer_confirmed:
            add(
                "warning",
                "answer_not_confirmed",
                f"{label}: đáp án chưa được xác nhận — sẽ lưu là “chưa xác nhận”.",
            )
        if (
            q.site_answer is not None
            and q.correct_answer is not None
            and q.site_answer != q.correct_answer
        ):
            add("info", "differs_from_site", f"{label}: đáp án khác với đáp án trang hiển thị.")

    used = {q.passage_key for q in included if q.passage_key}
    for p in content.passages:
        if p.key not in used:
            issues.append(
                Issue(
                    severity="info",
                    code="unused_passage",
                    message=f"Đoạn văn {p.key} chưa gắn câu hỏi nào.",
                )
            )
        if not p.content.strip():
            issues.append(
                Issue(severity="error", code="empty_passage", message=f"Đoạn văn {p.key} bị trống.")
            )

    issues.extend(attempt_issues(content))
    return issues


def attempt_issues(content: DraftContent) -> list[Issue]:
    att = content.attempt
    if not att.create:
        return []
    out: list[Issue] = []
    if att.started_at is None or att.completed_at is None:
        out.append(
            Issue(
                severity="error",
                code="attempt_times_required",
                message=(
                    "Để tạo bài làm, hãy nhập thời điểm bắt đầu và nộp bài (không tự suy đoán)."
                ),
            )
        )
    else:
        out.extend(_time_issues(att.started_at, att.completed_at))
    answered = [q for q in content.questions if q.include and q.user_answer is not None]
    if not answered:
        out.append(
            Issue(
                severity="error",
                code="attempt_no_answers",
                message="Không có lựa chọn nào của bạn trong dữ liệu nhập, không thể tạo bài làm.",
            )
        )
    return out


def _time_issues(started: datetime, completed: datetime) -> list[Issue]:
    if completed < started:
        return [
            Issue(
                severity="error",
                code="attempt_time_order",
                message="Thời điểm nộp bài trước thời điểm bắt đầu.",
            )
        ]
    if completed > utcnow() + CLOCK_SKEW:
        return [
            Issue(
                severity="error",
                code="attempt_in_future",
                message="Thời gian làm bài không được ở tương lai.",
            )
        ]
    return []


def summarize(content: DraftContent, issues: list[Issue]) -> DraftSummary:
    included = [q for q in content.questions if q.include]
    error_keys = {i.question_key for i in issues if i.severity == "error" and i.question_key}
    return DraftSummary(
        total_questions=len(content.questions),
        included_questions=len(included),
        valid_questions=sum(q.key not in error_keys for q in included),
        missing_answer=sum(q.correct_answer is None for q in included),
        needs_review=sum(bool(q.parser_notes) and not q.reviewed for q in included),
        confirmed_answers=sum(q.answer_confirmed for q in included),
        with_user_answer=sum(q.user_answer is not None for q in included),
        errors=sum(i.severity == "error" for i in issues),
        warnings=sum(i.severity == "warning" for i in issues),
    )
