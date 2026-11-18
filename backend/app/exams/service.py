"""Business logic for exams, passages and questions. Routers stay thin; all writes go here."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.responses import PageParams
from app.database.enums import AnswerSource, AnswerStatus
from app.exams.fingerprints import question_content_hash, question_fingerprint
from app.exams.models import Exam, ExamSource, Passage, Question
from app.exams.schemas import (
    ExamCreate,
    ExamListFilters,
    ExamRead,
    ExamSourceCreate,
    ExamUpdate,
    PassageCreate,
    QuestionCreate,
    QuestionUpdate,
)
from app.explanations.context import current_content_hash
from app.explanations.models import AIExplanation


# ---------------------------------------------------------------- exam sources
def list_sources(db: Session) -> list[ExamSource]:
    return list(db.scalars(select(ExamSource).order_by(ExamSource.name)))


def create_source(db: Session, data: ExamSourceCreate) -> ExamSource:
    clash = db.scalar(
        select(ExamSource).where(
            or_(ExamSource.name == data.name, ExamSource.base_url == data.base_url)
        )
    )
    if clash:
        raise ConflictError("Nguồn đề với tên hoặc URL này đã tồn tại.")
    source = ExamSource(name=data.name, base_url=data.base_url)
    db.add(source)
    db.commit()
    return source


# ----------------------------------------------------------------------- exams
@dataclass(frozen=True, slots=True)
class _ExamStats:
    question_count: int
    verified_answer_count: int
    attempt_count: int = 0
    latest_attempt_started_at: datetime | None = None
    latest_attempt_accuracy: float | None = None
    approved_explanation_count: int = 0


def _question_stats_subquery() -> Select[tuple[uuid.UUID, int, int]]:
    return select(
        Question.exam_id,
        func.count(Question.id).label("question_count"),
        func.count(Question.id)
        .filter(Question.answer_status == AnswerStatus.VERIFIED.value)
        .label("verified_answer_count"),
    ).group_by(Question.exam_id)


def _to_read(exam: Exam, stats: _ExamStats) -> ExamRead:
    return ExamRead.model_validate(
        {
            "id": exam.id,
            "source_id": exam.source_id,
            "source_name": exam.source.name if exam.source else None,
            "source_url": exam.source_url,
            "level": exam.level,
            "category": exam.category,
            "title": exam.title,
            "description": exam.description,
            "status": exam.status,
            "question_count": stats.question_count,
            "verified_answer_count": stats.verified_answer_count,
            "attempt_count": stats.attempt_count,
            "latest_attempt_started_at": stats.latest_attempt_started_at,
            "latest_attempt_accuracy": stats.latest_attempt_accuracy,
            "approved_explanation_count": stats.approved_explanation_count,
            "created_at": exam.created_at,
            "updated_at": exam.updated_at,
        }
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_exams(
    db: Session, filters: ExamListFilters, page: PageParams
) -> tuple[list[ExamRead], int]:
    conditions = []
    if filters.q:
        pattern = f"%{_escape_like(filters.q)}%"
        conditions.append(
            or_(
                Exam.title.ilike(pattern, escape="\\"), Exam.description.ilike(pattern, escape="\\")
            )
        )
    if filters.category:
        conditions.append(Exam.category == filters.category.value)
    if filters.status:
        conditions.append(Exam.status == filters.status.value)
    if filters.level:
        conditions.append(Exam.level == filters.level.value)

    total = db.scalar(select(func.count()).select_from(Exam).where(*conditions)) or 0
    stats = _question_stats_subquery().subquery()
    rows = db.execute(
        select(
            Exam,
            func.coalesce(stats.c.question_count, 0),
            func.coalesce(stats.c.verified_answer_count, 0),
        )
        .outerjoin(stats, stats.c.exam_id == Exam.id)
        .where(*conditions)
        .order_by(Exam.created_at.desc(), Exam.id)
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    if not rows:
        return [], total

    exam_ids = [exam.id for exam, _, _ in rows]
    attempt_counts: dict[uuid.UUID, int] = {
        exam_id: count
        for exam_id, count in db.execute(
            select(ExamAttempt.exam_id, func.count(ExamAttempt.id))
            .where(ExamAttempt.exam_id.in_(exam_ids))
            .group_by(ExamAttempt.exam_id)
        ).all()
    }
    latest_ranked = (
        select(
            ExamAttempt.exam_id.label("exam_id"),
            ExamAttempt.started_at.label("started_at"),
            ExamAttempt.correct_count.label("correct_count"),
            ExamAttempt.incorrect_count.label("incorrect_count"),
            func.row_number()
            .over(
                partition_by=ExamAttempt.exam_id,
                order_by=(ExamAttempt.started_at.desc(), ExamAttempt.id.desc()),
            )
            .label("position"),
        )
        .where(ExamAttempt.exam_id.in_(exam_ids))
        .subquery()
    )
    latest_by_exam = {
        exam_id: (started_at, correct_count, incorrect_count)
        for exam_id, started_at, correct_count, incorrect_count in db.execute(
            select(
                latest_ranked.c.exam_id,
                latest_ranked.c.started_at,
                latest_ranked.c.correct_count,
                latest_ranked.c.incorrect_count,
            ).where(latest_ranked.c.position == 1)
        ).all()
    }

    questions = list(db.scalars(select(Question).where(Question.exam_id.in_(exam_ids))))
    hash_by_question = {
        q.id: current_content_hash(db, q)
        for q in questions
        if q.correct_answer is not None and q.answer_status == AnswerStatus.VERIFIED.value
    }
    approved = set()
    if hash_by_question:
        approved = set(
            db.execute(
                select(AIExplanation.question_id, AIExplanation.content_hash).where(
                    AIExplanation.question_id.in_(hash_by_question),
                    AIExplanation.verification_status == "approved",
                )
            ).all()
        )
    approved_counts: dict[uuid.UUID, int] = {}
    for q in questions:
        if (q.id, hash_by_question.get(q.id)) in approved:
            approved_counts[q.exam_id] = approved_counts.get(q.exam_id, 0) + 1

    results = []
    for exam, qc, vc in rows:
        latest = latest_by_exam.get(exam.id)
        latest_accuracy = None
        if latest:
            graded = latest[1] + latest[2]
            latest_accuracy = round(latest[1] / graded, 4) if graded else None
        results.append(
            _to_read(
                exam,
                _ExamStats(
                    qc,
                    vc,
                    attempt_counts.get(exam.id, 0),
                    latest[0] if latest else None,
                    latest_accuracy,
                    approved_counts.get(exam.id, 0),
                ),
            )
        )
    return results, total


def get_exam_model(db: Session, exam_id: uuid.UUID, *, for_update: bool = False) -> Exam:
    stmt = select(Exam).where(Exam.id == exam_id)
    if for_update:
        stmt = stmt.with_for_update(of=Exam)
    exam = db.scalar(stmt)
    if exam is None:
        raise NotFoundError("Không tìm thấy đề thi.", details={"exam_id": str(exam_id)})
    return exam


def get_exam(db: Session, exam_id: uuid.UUID) -> ExamRead:
    exam = get_exam_model(db, exam_id)
    row = db.execute(_question_stats_subquery().where(Question.exam_id == exam_id)).first()
    stats = _ExamStats(row.question_count, row.verified_answer_count) if row else _ExamStats(0, 0)
    return _to_read(exam, stats)


def _ensure_source_exists(db: Session, source_id: uuid.UUID | None) -> None:
    if source_id is not None and db.get(ExamSource, source_id) is None:
        raise DomainValidationError(
            "Nguồn đề không tồn tại.", details={"source_id": str(source_id)}
        )


def _ensure_source_url_free(
    db: Session, source_url: str | None, exclude_exam_id: uuid.UUID | None = None
) -> None:
    if source_url is None:
        return
    stmt = select(Exam.id).where(Exam.source_url == source_url)
    if exclude_exam_id:
        stmt = stmt.where(Exam.id != exclude_exam_id)
    existing = db.scalar(stmt)
    if existing:
        raise ConflictError(
            "Đã có đề thi với URL nguồn này.", details={"existing_exam_id": str(existing)}
        )


def create_exam(db: Session, data: ExamCreate) -> ExamRead:
    _ensure_source_exists(db, data.source_id)
    _ensure_source_url_free(db, data.source_url)
    exam = Exam(
        title=data.title,
        level=data.level.value,
        category=data.category.value,
        description=data.description or None,
        source_url=data.source_url,
        source_id=data.source_id,
        status=data.status.value,
    )
    db.add(exam)
    db.commit()
    return get_exam(db, exam.id)


def update_exam(db: Session, exam_id: uuid.UUID, data: ExamUpdate) -> ExamRead:
    exam = get_exam_model(db, exam_id, for_update=True)
    changes = data.model_dump(exclude_unset=True)
    if "source_id" in changes:
        _ensure_source_exists(db, changes["source_id"])
    if "source_url" in changes:
        _ensure_source_url_free(db, changes["source_url"], exclude_exam_id=exam_id)
    if "description" in changes and changes["description"] == "":
        changes["description"] = None
    for field, value in changes.items():
        setattr(exam, field, value.value if hasattr(value, "value") else value)
    db.commit()
    db.expire(exam)
    return get_exam(db, exam_id)


# -------------------------------------------------------------------- passages
def list_passages(db: Session, exam_id: uuid.UUID) -> list[Passage]:
    get_exam_model(db, exam_id)
    return list(
        db.scalars(select(Passage).where(Passage.exam_id == exam_id).order_by(Passage.created_at))
    )


def create_passage(db: Session, exam_id: uuid.UUID, data: PassageCreate) -> Passage:
    get_exam_model(db, exam_id, for_update=True)
    passage = Passage(exam_id=exam_id, content=data.content)
    db.add(passage)
    db.commit()
    return passage


# ------------------------------------------------------------------- questions
def list_questions(db: Session, exam_id: uuid.UUID, page: PageParams) -> tuple[list[Question], int]:
    get_exam_model(db, exam_id)
    total = db.scalar(select(func.count(Question.id)).where(Question.exam_id == exam_id)) or 0
    items = list(
        db.scalars(
            select(Question)
            .where(Question.exam_id == exam_id)
            .order_by(Question.question_number)
            .offset(page.offset)
            .limit(page.page_size)
        )
    )
    return items, total


def get_question_model(
    db: Session, question_id: uuid.UUID, *, for_update: bool = False
) -> Question:
    stmt = select(Question).where(Question.id == question_id)
    if for_update:
        stmt = stmt.with_for_update()
    question = db.scalar(stmt)
    if question is None:
        raise NotFoundError("Không tìm thấy câu hỏi.", details={"question_id": str(question_id)})
    return question


def _ensure_passage_in_exam(db: Session, exam_id: uuid.UUID, passage_id: uuid.UUID | None) -> None:
    if passage_id is None:
        return
    found = db.scalar(
        select(Passage.id).where(Passage.id == passage_id, Passage.exam_id == exam_id)
    )
    if found is None:
        raise DomainValidationError(
            "Đoạn văn không thuộc đề thi này.", details={"passage_id": str(passage_id)}
        )


def _ensure_question_unique(
    db: Session,
    exam_id: uuid.UUID,
    question_number: int,
    content_hash: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    base = select(Question.id).where(Question.exam_id == exam_id)
    if exclude_id:
        base = base.where(Question.id != exclude_id)
    if db.scalar(base.where(Question.question_number == question_number)):
        raise ConflictError(
            f"Câu số {question_number} đã tồn tại trong đề này.",
            details={"field": "question_number"},
        )
    if db.scalar(base.where(Question.content_hash == content_hash)):
        raise ConflictError(
            "Câu hỏi có nội dung và lựa chọn giống hệt đã tồn tại trong đề này.",
            details={"field": "question_text"},
        )


def create_question(db: Session, exam_id: uuid.UUID, data: QuestionCreate) -> Question:
    # Lock the exam row so concurrent inserts for the same exam serialise cleanly.
    get_exam_model(db, exam_id, for_update=True)
    _ensure_passage_in_exam(db, exam_id, data.passage_id)
    content_hash = question_content_hash(data.passage_id, data.question_text, data.options)
    _ensure_question_unique(db, exam_id, data.question_number, content_hash)
    assert data.answer_status is not None  # filled by the schema validator
    question = Question(
        exam_id=exam_id,
        passage_id=data.passage_id,
        question_number=data.question_number,
        question_type=data.question_type.value,
        question_text=data.question_text,
        options=data.options,
        correct_answer=data.correct_answer,
        answer_status=data.answer_status.value,
        answer_source=AnswerSource.MANUAL.value if data.correct_answer is not None else None,
        content_hash=content_hash,
        fingerprint=question_fingerprint(data.question_text, data.options),
    )
    db.add(question)
    db.commit()
    return question


def update_question(db: Session, question_id: uuid.UUID, data: QuestionUpdate) -> Question:
    question = get_question_model(db, question_id, for_update=True)
    changes = data.model_dump(exclude_unset=True)

    options: list[str] = changes.get("options", question.options)
    correct_answer = changes.get("correct_answer", question.correct_answer)
    passage_id = changes.get("passage_id", question.passage_id)

    if "answer_status" in changes:
        answer_status = changes["answer_status"]
        if answer_status is None:
            raise DomainValidationError("'answer_status' cannot be null")
    elif "correct_answer" in changes:
        # Changing the key resets trust unless the caller re-confirms it in the same request.
        answer_status = AnswerStatus.MISSING if correct_answer is None else AnswerStatus.UNVERIFIED
    else:
        answer_status = AnswerStatus(question.answer_status)

    try:
        QuestionUpdate.check_answer(options, correct_answer, answer_status)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc

    _ensure_passage_in_exam(db, question.exam_id, passage_id)
    content_hash = question_content_hash(
        passage_id, changes.get("question_text", question.question_text), options
    )
    _ensure_question_unique(
        db,
        question.exam_id,
        changes.get("question_number", question.question_number),
        content_hash,
        exclude_id=question.id,
    )

    for field in ("question_number", "question_text", "options", "passage_id"):
        if field in changes:
            setattr(question, field, changes[field])
    if "question_type" in changes:
        question.question_type = changes["question_type"].value
    if correct_answer is None:
        question.answer_source = None
    elif (
        "correct_answer" in changes and correct_answer != question.correct_answer
    ) or question.answer_source is None:
        question.answer_source = AnswerSource.MANUAL.value
    question.correct_answer = correct_answer
    question.answer_status = AnswerStatus(answer_status).value
    question.content_hash = content_hash
    question.fingerprint = question_fingerprint(question.question_text, list(question.options))
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: uuid.UUID) -> None:
    question = get_question_model(db, question_id, for_update=True)
    used = db.scalar(select(exists().where(AttemptAnswer.question_id == question_id)))
    if used:
        raise ConflictError(
            "Không thể xoá câu hỏi đã có trong lịch sử làm bài.",
            details={"question_id": str(question_id)},
        )
    db.delete(question)
    db.commit()
