"""Input for practice generation: an *active* knowledge item backed by approved explanations."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError, NotFoundError
from app.database.enums import KnowledgeLink, KnowledgeStatus, PracticeStatus, VerificationStatus
from app.exams.models import Question
from app.explanations.models import AIExplanation
from app.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeRelationLink,
    QuestionKnowledge,
)
from app.practice.models import GeneratedPracticeQuestion

MAX_PER_REQUEST = 5
QUESTION_TYPES = {
    "grammar": "grammar_form",
    "vocabulary": "contextual_definition",
    "kanji": "kanji_reading",
    "reading_skill": "reading_short",
}


@dataclass(frozen=True)
class PracticeContext:
    knowledge_id: uuid.UUID
    knowledge_type: str
    title: str
    summary: str
    details: dict[str, Any]
    confusions: list[dict[str, str]]
    approved_takeaways: list[str]
    avoid_questions: list[dict[str, Any]]  # source questions + existing practice
    question_type: str
    count: int
    source_explanation_id: uuid.UUID | None


def build(
    db: Session, knowledge_id: uuid.UUID, count: int, question_type: str | None
) -> PracticeContext:
    k = db.get(KnowledgeItem, knowledge_id)
    if k is None:
        raise NotFoundError("Không tìm thấy mục kiến thức.")
    if k.status != KnowledgeStatus.ACTIVE:
        raise DomainValidationError("Chỉ tạo câu luyện cho mục kiến thức đang hoạt động.")
    if k.knowledge_type == "reading_skill":
        raise DomainValidationError(
            "Chưa hỗ trợ tạo câu luyện đọc hiểu (cần đoạn văn mới đã được kiểm chứng)."
        )
    if not 1 <= count <= MAX_PER_REQUEST:
        raise DomainValidationError(f"Số câu mỗi lần từ 1 đến {MAX_PER_REQUEST}.")
    approved = [
        e
        for e in db.scalars(
            select(AIExplanation)
            .join(KnowledgeEvidence, KnowledgeEvidence.explanation_id == AIExplanation.id)
            .where(
                KnowledgeEvidence.knowledge_id == k.id,
                AIExplanation.verification_status == VerificationStatus.APPROVED.value,
            )
            .order_by(AIExplanation.created_at.desc())
        )
    ]
    if not approved:
        raise DomainValidationError(
            "Mục này chưa có lời giải đã duyệt làm nguồn; không tạo câu luyện."
        )
    confusions = []
    for rel in db.scalars(
        select(KnowledgeRelationLink).where(
            KnowledgeRelationLink.relation_type == KnowledgeLink.CONFUSED_WITH.value,
            or_(KnowledgeRelationLink.source_id == k.id, KnowledgeRelationLink.target_id == k.id),
        )
    ):
        other = db.get(KnowledgeItem, rel.target_id if rel.source_id == k.id else rel.source_id)
        if other is not None and other.status == KnowledgeStatus.ACTIVE:
            confusions.append({"title": other.title, "summary": other.content})
    avoid: list[dict[str, Any]] = [
        {"question_text": q.question_text, "options": list(q.options)}
        for q in db.scalars(
            select(Question)
            .join(QuestionKnowledge, QuestionKnowledge.question_id == Question.id)
            .where(QuestionKnowledge.knowledge_id == k.id)
        )
    ]
    avoid += [
        {"question_text": p.question_text, "options": list(p.options)}
        for p in db.scalars(
            select(GeneratedPracticeQuestion).where(
                GeneratedPracticeQuestion.knowledge_id == k.id,
                GeneratedPracticeQuestion.status != PracticeStatus.REJECTED.value,
            )
        )
    ]
    takeaways = []
    for e in approved[:3]:
        takeaway = (e.explanation_json or {}).get("key_takeaway")
        if takeaway:
            takeaways.append(str(takeaway))
    return PracticeContext(
        knowledge_id=k.id,
        knowledge_type=k.knowledge_type,
        title=k.title,
        summary=k.content,
        details=k.details,
        confusions=confusions,
        approved_takeaways=takeaways,
        avoid_questions=avoid,
        question_type=question_type or QUESTION_TYPES[k.knowledge_type],
        count=count,
        source_explanation_id=approved[0].id,
    )
