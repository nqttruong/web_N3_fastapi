"""Attempt submission and grading.

Grading rules (applied once, at submission, inside one transaction):

* unanswered (``selected_answer`` is null)          -> is_correct NULL, counted as *unanswered*
* answered, question has no **verified** key        -> is_correct NULL, counted as *ungraded*
* answered, verified key, selection == key          -> is_correct TRUE  (*correct*)
* answered, verified key, selection != key          -> is_correct FALSE (*incorrect*)

The verified key is snapshotted into ``attempt_answers.correct_answer_snapshot`` so later edits
to a question never rewrite history.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import Text, func, select, tuple_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.attempts.schemas import (
    AttemptAnswerRead,
    AttemptCreate,
    AttemptDetail,
    AttemptSummary,
    MistakeRead,
    accuracy,
)
from app.core.errors import DomainValidationError, NotFoundError
from app.core.responses import PageParams
from app.core.time import utcnow
from app.database.enums import AttemptSource, ExamStatus
from app.exams.models import Exam, Question
from app.exams.service import get_exam_model
from app.explanations.context import current_content_hash
from app.explanations.models import AIExplanation

CLOCK_SKEW = timedelta(minutes=5)


def _summary(attempt: ExamAttempt, exam: Exam) -> dict[str, object]:
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_title": exam.title,
        "exam_category": exam.category,
        "started_at": attempt.started_at,
        "completed_at": attempt.completed_at,
        "total_questions": attempt.total_questions,
        "correct_count": attempt.correct_count,
        "incorrect_count": attempt.incorrect_count,
        "unanswered_count": attempt.unanswered_count,
        "ungraded_count": attempt.ungraded_count,
        "source": attempt.source,
        "accuracy": accuracy(attempt.correct_count, attempt.incorrect_count),
        "created_at": attempt.created_at,
    }


def create_attempt(db: Session, data: AttemptCreate) -> AttemptDetail:
    completed_at = data.completed_at or utcnow()
    check_attempt_times(data.started_at, completed_at)

    # Lock the exam so its question set cannot change while we grade.
    try:
        exam = get_exam_model(db, data.exam_id, for_update=True)
    except NotFoundError as exc:
        raise DomainValidationError(
            "Đề thi không tồn tại.", details={"exam_id": str(data.exam_id)}
        ) from exc
    if exam.status == ExamStatus.ARCHIVED:
        raise DomainValidationError("Không thể làm đề đã lưu trữ.")

    questions = list(
        db.scalars(
            select(Question).where(Question.exam_id == exam.id).order_by(Question.question_number)
        )
    )
    if not questions:
        raise DomainValidationError("Đề thi chưa có câu hỏi nào.")

    by_id = {q.id: q for q in questions}
    selections: dict[uuid.UUID, int | None] = {}
    errors: list[dict[str, object]] = []
    for index, answer in enumerate(data.answers):
        question = by_id.get(answer.question_id)
        if question is None:
            errors.append(
                {"loc": ["answers", index, "question_id"], "msg": "Câu hỏi không thuộc đề này."}
            )
            continue
        if answer.selected_answer is not None and answer.selected_answer > len(question.options):
            errors.append(
                {
                    "loc": ["answers", index, "selected_answer"],
                    "msg": f"Lựa chọn phải nằm trong khoảng 1–{len(question.options)}.",
                }
            )
            continue
        selections[question.id] = answer.selected_answer
    if errors:
        raise DomainValidationError("Bài làm không hợp lệ.", details=errors)

    attempt = build_graded_attempt(
        exam=exam,
        questions=questions,
        selections=selections,
        started_at=data.started_at,
        completed_at=completed_at,
    )
    db.add(attempt)
    db.commit()  # attempt + all answers in one transaction
    return get_attempt(db, attempt.id)


def check_attempt_times(started_at: datetime, completed_at: datetime) -> None:
    now = utcnow()
    if completed_at < started_at:
        raise DomainValidationError("started_at không được sau thời điểm nộp bài.")
    if started_at > now + CLOCK_SKEW or completed_at > now + CLOCK_SKEW:
        raise DomainValidationError("Thời gian làm bài không được ở tương lai.")


def build_graded_attempt(
    *,
    exam: Exam,
    questions: list[Question],
    selections: dict[uuid.UUID, int | None],
    started_at: datetime,
    completed_at: datetime,
    source: AttemptSource = AttemptSource.PRACTICE,
    import_draft_id: uuid.UUID | None = None,
) -> ExamAttempt:
    """Grade ``selections`` against the *verified* keys of ``questions`` (all questions of the
    exam). Does not add to the session or commit: callers own the transaction."""
    attempt = ExamAttempt(
        exam_id=exam.id,
        started_at=started_at,
        completed_at=completed_at,
        total_questions=len(questions),
        correct_count=0,
        incorrect_count=0,
        unanswered_count=0,
        ungraded_count=0,
        source=source.value,
        import_draft_id=import_draft_id,
    )
    for question in questions:
        selected = selections.get(question.id)
        key = question.verified_answer
        is_correct = None if selected is None or key is None else selected == key
        if selected is None:
            attempt.unanswered_count += 1
        elif is_correct is None:
            attempt.ungraded_count += 1
        elif is_correct:
            attempt.correct_count += 1
        else:
            attempt.incorrect_count += 1
        attempt.answers.append(
            AttemptAnswer(
                exam_id=exam.id,
                question_id=question.id,
                question_number=question.question_number,
                selected_answer=selected,
                correct_answer_snapshot=key,
                is_correct=is_correct,
            )
        )
    return attempt


def list_attempts(
    db: Session, page: PageParams, exam_id: uuid.UUID | None = None
) -> tuple[list[AttemptSummary], int]:
    conditions = [ExamAttempt.exam_id == exam_id] if exam_id else []
    total = db.scalar(select(func.count()).select_from(ExamAttempt).where(*conditions)) or 0
    rows = db.execute(
        select(ExamAttempt, Exam)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(*conditions)
        .order_by(ExamAttempt.started_at.desc(), ExamAttempt.id)
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    if not rows:
        return [], total
    attempt_ids = [attempt.id for attempt, _ in rows]
    wrong_answers = db.execute(
        select(AttemptAnswer, Question)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .where(AttemptAnswer.attempt_id.in_(attempt_ids), AttemptAnswer.is_correct.is_(False))
    ).all()
    hashes = {
        question.id: current_content_hash(db, question)
        for _, question in wrong_answers
        if question.correct_answer is not None and question.answer_status == "verified"
    }
    statuses: dict[uuid.UUID, str] = {}
    if hashes:
        explanation_rows = db.execute(
            select(AIExplanation.question_id, AIExplanation.verification_status).where(
                tuple_(AIExplanation.question_id, AIExplanation.content_hash).in_(
                    list(hashes.items())
                ),
                AIExplanation.verification_status.in_(["generated", "needs_review", "approved"]),
            )
        ).all()
        for question_id, status in explanation_rows:
            previous = statuses.get(question_id)
            if previous != "approved":
                statuses[question_id] = status
    counts: dict[uuid.UUID, list[int]] = {}
    for answer, question in wrong_answers:
        status = statuses.get(question.id)
        if status:
            bucket = counts.setdefault(answer.attempt_id, [0, 0])
            bucket[0 if status == "approved" else 1] += 1
    return [
        AttemptSummary.model_validate(
            {
                **_summary(attempt, exam),
                "approved_explanation_count": counts.get(attempt.id, [0, 0])[0],
                "pending_explanation_count": counts.get(attempt.id, [0, 0])[1],
            }
        )
        for attempt, exam in rows
    ], total


def list_mistakes(
    db: Session,
    page: PageParams,
    *,
    exam_id: uuid.UUID | None = None,
    skill: str | None = None,
    q: str | None = None,
) -> tuple[list[MistakeRead], int]:
    """List one current notebook row per question, derived from immutable wrong answers.

    Blank and ungraded answers are intentionally excluded. Notebook mastery/archive state is
    local-only in N3 Sensei and is not fabricated here.
    """
    from sqlalchemy import case, or_

    from app.database.enums import ExamCategory, QuestionType

    kanji = (QuestionType.KANJI_READING.value, QuestionType.ORTHOGRAPHY.value)
    grammar = (
        QuestionType.GRAMMAR_FORM.value,
        QuestionType.SENTENCE_COMPOSITION.value,
        QuestionType.TEXT_GRAMMAR.value,
    )
    reading = (
        QuestionType.READING_SHORT.value,
        QuestionType.READING_MEDIUM.value,
        QuestionType.READING_LONG.value,
        QuestionType.INFORMATION_RETRIEVAL.value,
    )
    skill_expr = case(
        (Question.question_type.in_(kanji), ExamCategory.KANJI.value),
        (Question.question_type.in_(grammar), ExamCategory.GRAMMAR.value),
        (Question.question_type.in_(reading), ExamCategory.READING.value),
        (Question.question_type == QuestionType.OTHER.value, Exam.category),
        else_=ExamCategory.VOCABULARY.value,
    )
    conditions: list[ColumnElement[bool]] = [AttemptAnswer.is_correct.is_(False)]
    if exam_id is not None:
        conditions.append(ExamAttempt.exam_id == exam_id)
    if skill is not None:
        conditions.append(skill_expr == skill)
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                Question.question_text.ilike(pattern),
                Exam.title.ilike(pattern),
                Question.options.cast(Text).ilike(pattern),
            )
        )

    grouped = (
        select(
            Question.id.label("question_id"),
            func.count(AttemptAnswer.id).label("occurrences"),
            func.min(ExamAttempt.started_at).label("first_wrong_at"),
            func.max(ExamAttempt.started_at).label("last_wrong_at"),
        )
        .join(AttemptAnswer, AttemptAnswer.question_id == Question.id)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(*conditions)
        .group_by(Question.id)
        .subquery()
    )
    total = db.scalar(select(func.count()).select_from(grouped)) or 0
    page_groups = list(
        db.execute(
            select(grouped)
            .order_by(grouped.c.last_wrong_at.desc(), grouped.c.question_id)
            .offset(page.offset)
            .limit(page.page_size)
        )
    )
    if not page_groups:
        return [], total
    stats = {row.question_id: row for row in page_groups}
    latest_rows = db.execute(
        select(AttemptAnswer, Question, ExamAttempt, Exam)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(
            AttemptAnswer.is_correct.is_(False),
            Question.id.in_(list(stats)),
            *([ExamAttempt.exam_id == exam_id] if exam_id is not None else []),
        )
        .order_by(ExamAttempt.started_at.desc(), AttemptAnswer.id)
    ).all()
    latest: dict[uuid.UUID, tuple[AttemptAnswer, Question, ExamAttempt, Exam]] = {}
    for answer, question, attempt, exam in latest_rows:
        latest.setdefault(question.id, (answer, question, attempt, exam))

    items: list[MistakeRead] = []
    for question_id in stats:
        answer, question, attempt, exam = latest[question_id]
        items.append(
            MistakeRead.model_validate(
                {
                    "question_id": question.id,
                    "exam_id": exam.id,
                    "exam_title": exam.title,
                    "exam_category": exam.category,
                    "question_number": answer.question_number,
                    "question_type": question.question_type,
                    "question_text": question.question_text,
                    "options": question.options,
                    "passage_id": question.passage_id,
                    "occurrences": stats[question_id].occurrences,
                    "first_wrong_at": stats[question_id].first_wrong_at,
                    "last_wrong_at": stats[question_id].last_wrong_at,
                    "latest_attempt_id": attempt.id,
                    "latest_attempt_answer_id": answer.id,
                    "latest_attempt_started_at": attempt.started_at,
                    "latest_selected_answer": answer.selected_answer,
                    "correct_answer_at_submission": answer.correct_answer_snapshot,
                    "current_answer_status": question.answer_status,
                }
            )
        )
    return items, total


def get_attempt(db: Session, attempt_id: uuid.UUID) -> AttemptDetail:
    row = db.execute(
        select(ExamAttempt, Exam)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(ExamAttempt.id == attempt_id)
    ).first()
    if row is None:
        raise NotFoundError("Không tìm thấy bài làm.", details={"attempt_id": str(attempt_id)})
    attempt, exam = row
    answer_rows = db.execute(
        select(AttemptAnswer, Question)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .where(AttemptAnswer.attempt_id == attempt_id)
        .order_by(AttemptAnswer.question_number)
    ).all()
    answers = [
        AttemptAnswerRead(
            question_id=q.id,
            question_number=a.question_number,
            question_type=q.question_type,
            question_text=q.question_text,
            options=q.options,
            passage_id=q.passage_id,
            selected_answer=a.selected_answer,
            correct_answer=a.correct_answer_snapshot,
            is_correct=a.is_correct,
            current_answer_status=q.answer_status,
        )
        for a, q in answer_rows
    ]
    return AttemptDetail.model_validate(
        {**_summary(attempt, exam), "exam_source_url": exam.source_url, "answers": answers}
    )
