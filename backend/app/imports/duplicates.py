"""Duplicate detection against existing data. Reports only — never merges or deletes.

Distinguishes:
* duplicate exam      — same source URL, or every included question already belongs to one exam
* duplicate question  — the same question (fingerprint) exists in another exam
* re-import           — the same raw input was imported before (another draft)
* new attempt         — the matching exam already has attempts; committing adds one more and
                        never touches earlier history
"""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.attempts.models import ExamAttempt
from app.exams.fingerprints import question_fingerprint
from app.exams.models import Exam, Question
from app.imports.models import ImportDraft
from app.imports.schemas import DraftContent, Issue


def _exam_info(db: Session, exam_ids: Sequence[object]) -> dict[object, dict[str, object]]:
    if not exam_ids:
        return {}
    rows = db.execute(
        select(
            Exam.id,
            Exam.title,
            select(func.count(Question.id))
            .where(Question.exam_id == Exam.id)
            .correlate(Exam)
            .scalar_subquery(),
            select(func.count(ExamAttempt.id))
            .where(ExamAttempt.exam_id == Exam.id)
            .correlate(Exam)
            .scalar_subquery(),
        ).where(Exam.id.in_(exam_ids))
    ).all()
    return {
        r[0]: {"exam_id": str(r[0]), "title": r[1], "question_count": r[2], "attempt_count": r[3]}
        for r in rows
    }


def duplicate_issues(db: Session, draft: ImportDraft, content: DraftContent) -> list[Issue]:
    issues: list[Issue] = []
    included = [q for q in content.questions if q.include and q.question_text.strip()]

    # 1. Same source URL
    if draft.source_url:
        same_url = list(db.scalars(select(Exam.id).where(Exam.source_url == draft.source_url)))
        for url_info in _exam_info(db, same_url).values():
            issues.append(
                Issue(
                    severity="warning",
                    code="duplicate_source_url",
                    message=(
                        f"Đã có đề “{url_info['title']}” với cùng URL nguồn "
                        f"({url_info['question_count']} câu, {url_info['attempt_count']} lần làm). "
                        "Hãy chọn “Dùng đề đã có” khi lưu để không tạo đề trùng."
                    ),
                    data=url_info,
                )
            )

    # 2. Same questions in existing exams (fingerprint excludes the passage)
    fps = {q.key: question_fingerprint(q.question_text, q.options) for q in included}
    if fps:
        rows = db.execute(
            select(Question.fingerprint, Question.exam_id).where(
                Question.fingerprint.in_(set(fps.values()))
            )
        ).all()
        exams_by_fp: dict[str, set[object]] = defaultdict(set)
        for fp, exam_id in rows:
            exams_by_fp[fp].add(exam_id)
        matched_per_exam: dict[object, int] = defaultdict(int)
        for key, fp in fps.items():
            for exam_id in exams_by_fp.get(fp, ()):
                matched_per_exam[exam_id] += 1
            if fp in exams_by_fp:
                issues.append(
                    Issue(
                        severity="info",
                        code="question_exists_elsewhere",
                        message="Câu hỏi này đã có trong một đề khác.",
                        question_key=key,
                        data={"exam_ids": sorted(str(e) for e in exams_by_fp[fp])},
                    )
                )
        info = _exam_info(db, list(matched_per_exam))
        already_flagged = {i.data["exam_id"] for i in issues if i.data and "exam_id" in i.data}
        for exam_id, matched in sorted(matched_per_exam.items(), key=lambda kv: -kv[1]):
            meta = info.get(exam_id)
            if meta is None:
                continue
            data = {**meta, "matched": matched, "total": len(included)}
            if matched == len(included) and str(exam_id) not in already_flagged:
                issues.append(
                    Issue(
                        severity="warning",
                        code="duplicate_exam",
                        message=(
                            f"Tất cả {matched} câu đã có trong đề “{meta['title']}”. "
                            "Có thể bạn đang nhập lại đề này — hãy dùng đề đã có."
                        ),
                        data=data,
                    )
                )
            elif matched < len(included):
                issues.append(
                    Issue(
                        severity="info",
                        code="questions_in_other_exam",
                        message=f"{matched}/{len(included)} câu đã có trong đề “{meta['title']}”.",
                        data=data,
                    )
                )
            if meta["attempt_count"]:
                issues.append(
                    Issue(
                        severity="info",
                        code="existing_attempts",
                        message=(
                            f"Đề “{meta['title']}” đã có {meta['attempt_count']} lần làm. "
                            "Bài làm nhập vào sẽ được thêm mới, lịch sử cũ giữ nguyên."
                        ),
                        data=meta,
                    )
                )

    # 3. Same raw input imported before
    others = db.execute(
        select(ImportDraft.id, ImportDraft.status, ImportDraft.exam_id).where(
            ImportDraft.raw_sha256 == draft.raw_sha256, ImportDraft.id != draft.id
        )
    ).all()
    for other_id, status, exam_id in others:
        issues.append(
            Issue(
                severity="info",
                code="duplicate_draft",
                message="Nội dung này đã được nhập trong một bản nháp khác.",
                data={
                    "draft_id": str(other_id),
                    "status": status,
                    "exam_id": str(exam_id) if exam_id else None,
                },
            )
        )
    return issues
