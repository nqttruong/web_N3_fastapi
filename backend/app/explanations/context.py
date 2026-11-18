"""Exact, database-backed input for one explanation request, plus eligibility rules.

Only data that exists in the database is used. The learner's selection is included only when
a real attempt answer is given — it is never guessed.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer
from app.core.errors import NotFoundError
from app.database.enums import AnswerStatus, QuestionType
from app.exams.models import Exam, Passage, Question
from app.explanations.payload import Category

READING_TYPES = {
    QuestionType.READING_SHORT,
    QuestionType.READING_MEDIUM,
    QuestionType.READING_LONG,
    QuestionType.INFORMATION_RETRIEVAL,
    QuestionType.TEXT_GRAMMAR,
}
KANJI_TYPES = {QuestionType.KANJI_READING, QuestionType.ORTHOGRAPHY}
GRAMMAR_TYPES = {QuestionType.GRAMMAR_FORM, QuestionType.SENTENCE_COMPOSITION}


def category_for(question_type: str) -> Category:
    qt = QuestionType(question_type)
    if qt in READING_TYPES:
        return "reading"
    if qt in KANJI_TYPES:
        return "kanji"
    if qt in GRAMMAR_TYPES:
        return "grammar"
    return "vocabulary"


@dataclass(frozen=True)
class QuestionContext:
    question_id: uuid.UUID
    exam_title: str
    exam_category: str
    source_url: str | None
    question_number: int
    question_type: str
    category: Category
    question_text: str
    options: list[str]
    passage: str | None
    verified_answer: int  # 1-based (DB convention)
    selected_answer: int | None  # 1-based, only from a real attempt answer
    content_hash: str

    @property
    def correct_index(self) -> int:
        return self.verified_answer - 1

    @property
    def selected_index(self) -> int | None:
        return None if self.selected_answer is None else self.selected_answer - 1


@dataclass(frozen=True)
class Ineligible:
    code: str
    message: str


def content_hash(
    question_text: str,
    options: list[str],
    passage: str | None,
    question_type: str,
    verified_answer: int | None,
) -> str:
    raw = json.dumps(
        {"t": question_text, "o": options, "p": passage, "q": question_type, "a": verified_answer},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def current_content_hash(db: Session, question: Question) -> str:
    passage = db.get(Passage, question.passage_id) if question.passage_id else None
    return content_hash(
        question.question_text,
        list(question.options),
        passage.content if passage else None,
        question.question_type,
        question.verified_answer,
    )


def check_eligibility(question: Question, passage: Passage | None) -> Ineligible | None:
    if question.answer_status != AnswerStatus.VERIFIED or question.correct_answer is None:
        return Ineligible(
            "answer_not_verified",
            "Câu này chưa có đáp án đã xác nhận. Hãy xác nhận đáp án trước khi chữa bằng AI.",
        )
    if QuestionType(question.question_type) in READING_TYPES and passage is None:
        return Ineligible(
            "missing_passage",
            "Câu đọc hiểu chưa gắn đoạn văn; không thể giải thích khẳng định khi thiếu ngữ cảnh.",
        )
    if len(question.options) < 2:
        return Ineligible("too_few_options", "Câu hỏi có ít hơn 2 lựa chọn.")
    return None


def load_question(db: Session, question_id: uuid.UUID) -> tuple[Question, Passage | None, Exam]:
    question = db.get(Question, question_id)
    if question is None:
        raise NotFoundError("Không tìm thấy câu hỏi.", details={"question_id": str(question_id)})
    passage = db.get(Passage, question.passage_id) if question.passage_id else None
    exam = db.get(Exam, question.exam_id)
    assert exam is not None
    return question, passage, exam


def selected_answer_for(
    db: Session, question_id: uuid.UUID, attempt_answer_id: uuid.UUID | None
) -> int | None:
    if attempt_answer_id is None:
        return None
    answer = db.scalar(
        select(AttemptAnswer).where(
            AttemptAnswer.id == attempt_answer_id, AttemptAnswer.question_id == question_id
        )
    )
    if answer is None:
        raise NotFoundError(
            "Câu trả lời không thuộc câu hỏi này.",
            details={"attempt_answer_id": str(attempt_answer_id)},
        )
    return answer.selected_answer


def build_context(
    db: Session, question_id: uuid.UUID, attempt_answer_id: uuid.UUID | None = None
) -> QuestionContext | Ineligible:
    question, passage, exam = load_question(db, question_id)
    problem = check_eligibility(question, passage)
    if problem is not None:
        return problem
    assert question.correct_answer is not None
    passage_text = passage.content if passage else None
    return QuestionContext(
        question_id=question.id,
        exam_title=exam.title,
        exam_category=exam.category,
        source_url=exam.source_url,
        question_number=question.question_number,
        question_type=question.question_type,
        category=category_for(question.question_type),
        question_text=question.question_text,
        options=list(question.options),
        passage=passage_text,
        verified_answer=question.correct_answer,
        selected_answer=selected_answer_for(db, question.id, attempt_answer_id),
        content_hash=content_hash(
            question.question_text,
            list(question.options),
            passage_text,
            question.question_type,
            question.correct_answer,
        ),
    )
