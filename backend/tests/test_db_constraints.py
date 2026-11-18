"""The database itself must reject invalid rows, even if a bug bypasses the API validation."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.exams.fingerprints import question_content_hash
from app.exams.models import Exam, Question


def _exam(db: Session, **kw: object) -> Exam:
    exam = Exam(title="t", category="grammar", **kw)
    db.add(exam)
    db.flush()
    return exam


def _question(db: Session, exam: Exam, number: int = 1, **kw: object) -> Question:
    fields: dict[str, object] = {
        "question_type": "grammar_form",
        "question_text": f"q{number}",
        "options": ["a", "b", "c", "d"],
        "content_hash": uuid.uuid4().hex,
        "fingerprint": uuid.uuid4().hex,
    } | kw
    q = Question(exam_id=exam.id, question_number=number, **fields)
    db.add(q)
    db.flush()
    return q


@pytest.mark.parametrize(
    "fields",
    [
        {"correct_answer": 5, "answer_status": "verified"},  # out of range of options
        {"correct_answer": 1, "answer_status": "missing"},
        {"correct_answer": None, "answer_status": "verified"},
        {"options": ["only"]},
        {"options": {"a": 1}},
        {"question_type": "listening"},
        {"question_text": "  "},
    ],
)
def test_question_check_constraints(db_session: Session, fields: dict[str, object]) -> None:
    exam = _exam(db_session)
    with pytest.raises(IntegrityError):
        _question(db_session, exam, **fields)
    db_session.rollback()


def test_exam_check_constraints(db_session: Session) -> None:
    for bad in ({"level": "N9"}, {"status": "deleted"}, {"source_url": "javascript:alert(1)"}):
        with pytest.raises(IntegrityError):
            _exam(db_session, **bad)
        db_session.rollback()


def test_attempt_answer_must_belong_to_same_exam(db_session: Session) -> None:
    exam_a, exam_b = _exam(db_session), _exam(db_session)
    foreign_q = _question(db_session, exam_b)
    attempt = ExamAttempt(
        exam_id=exam_a.id,
        started_at=exam_a.created_at,
        total_questions=1,
        correct_count=0,
        incorrect_count=0,
        unanswered_count=1,
        ungraded_count=0,
    )
    db_session.add(attempt)
    db_session.flush()
    db_session.add(
        AttemptAnswer(
            attempt_id=attempt.id,
            exam_id=exam_a.id,
            question_id=foreign_q.id,
            question_number=1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_attempt_counts_must_sum(db_session: Session) -> None:
    exam = _exam(db_session)
    db_session.add(
        ExamAttempt(
            exam_id=exam.id,
            started_at=exam.created_at,
            total_questions=3,
            correct_count=1,
            incorrect_count=0,
            unanswered_count=0,
            ungraded_count=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_content_hash_normalisation() -> None:
    a = question_content_hash(None, "ＡＢＣ　です", ["１", "２"])
    b = question_content_hash(None, "ABC です ", ["1", "2"])
    c = question_content_hash(None, "ABC です", ["1", "3"])
    assert a == b
    assert a != c
