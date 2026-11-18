"""Knowledge workflow: preview (extraction.py) → user confirmation → persist → review items."""

import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.database.enums import (
    KnowledgeLink,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    ReviewType,
    VerificationStatus,
)
from app.exams.models import Exam, Question
from app.explanations import service as explanations
from app.explanations.context import current_content_hash
from app.explanations.models import AIExplanation
from app.knowledge import extraction
from app.knowledge import normalize as nz
from app.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeRelationLink,
    QuestionKnowledge,
)
from app.knowledge.schemas import (
    ConfirmedItem,
    ConfirmRequest,
    ConfirmResult,
    EvidenceRead,
    KnowledgeDetail,
    KnowledgeListItem,
    KnowledgeStats,
    KnowledgeUpdate,
    LinkedQuestion,
    RelatedItem,
    ReviewItemBrief,
)
from app.reviews import service as reviews
from app.reviews.models import ReviewItem

ROLE_RANK = {
    KnowledgeRelation.TESTS: 3,
    KnowledgeRelation.DISTRACTOR: 2,
    KnowledgeRelation.CONTEXT: 1,
}
SYMMETRIC = {KnowledgeLink.CONFUSED_WITH, KnowledgeLink.RELATED_TO}
RECALL_TYPES = {KnowledgeType.GRAMMAR, KnowledgeType.VOCABULARY, KnowledgeType.KANJI}


def key_for(ktype: KnowledgeType, title: str, details: dict[str, Any]) -> str:
    """Server-side key (client keys are never trusted)."""
    if ktype == KnowledgeType.GRAMMAR:
        key = nz.grammar_key(details.get("pattern") or title)
        if key == "grammar:":
            raise DomainValidationError(f"Không xác định được mẫu ngữ pháp từ “{title}”.")
        return key
    if ktype == KnowledgeType.VOCABULARY:
        surface = details.get("surface") or title
        return nz.vocab_key(surface, details.get("reading") or surface)
    if ktype == KnowledgeType.KANJI:
        word, reading = details.get("word"), details.get("reading")
        if not word or not reading:
            raise DomainValidationError("Mục kanji cần từ (word) và cách đọc (reading).")
        return nz.kanji_key(word, reading)
    skill = details.get("skill")
    if skill not in nz.READING_SKILLS:
        raise DomainValidationError(
            "Hãy chọn kỹ năng đọc hợp lệ trước khi lưu.",
            details={"allowed": sorted(nz.READING_SKILLS)},
        )
    return nz.reading_key(skill)


def _next_sense_key(db: Session, ktype: KnowledgeType, key: str) -> str:
    base = nz.base_key(key)
    taken = set(
        db.scalars(
            select(KnowledgeItem.canonical_key).where(
                KnowledgeItem.knowledge_type == ktype.value,
                or_(
                    KnowledgeItem.canonical_key == base,
                    KnowledgeItem.canonical_key.like(f"{base}#%"),
                ),
            )
        )
    )
    n = 2
    while f"{base}#{n}" in taken:
        n += 1
    return f"{base}#{n}"


def _check_explanation(
    db: Session, question_id: uuid.UUID, explanation_id: uuid.UUID
) -> AIExplanation:
    q = db.get(Question, question_id)
    exp = db.get(AIExplanation, explanation_id)
    if q is None or exp is None or exp.question_id != question_id:
        raise DomainValidationError(
            "Lời giải không thuộc câu hỏi này.", details={"question_id": str(question_id)}
        )
    if exp.verification_status != VerificationStatus.APPROVED:
        raise ConflictError(
            "Chỉ dùng được lời giải đã được xác nhận.",
            details={"code": "explanation_not_approved", "question_id": str(question_id)},
        )
    if exp.content_hash != current_content_hash(db, q):
        raise ConflictError(
            "Lời giải đã cũ; hãy tạo và duyệt lời giải mới.",
            details={"code": "explanation_stale", "question_id": str(question_id)},
        )
    return exp


def _has_mistake(db: Session, question_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(AttemptAnswer.id)
            .where(AttemptAnswer.question_id == question_id, AttemptAnswer.is_correct.is_(False))
            .limit(1)
        )
        is not None
    )


def add_relation(
    db: Session,
    a: uuid.UUID,
    b: uuid.UUID,
    rel: KnowledgeLink,
    explanation_id: uuid.UUID | None = None,
) -> bool:
    if a == b:
        return False
    if rel in SYMMETRIC:
        a, b = sorted([a, b], key=str)
    exists = db.scalar(
        select(KnowledgeRelationLink.id).where(
            KnowledgeRelationLink.source_id == a,
            KnowledgeRelationLink.target_id == b,
            KnowledgeRelationLink.relation_type == rel.value,
        )
    )
    if exists:
        return False
    db.add(
        KnowledgeRelationLink(
            source_id=a, target_id=b, relation_type=rel.value, source_explanation_id=explanation_id
        )
    )
    db.flush()
    return True


def confirm(db: Session, req: ConfirmRequest) -> ConfirmResult:
    now = utcnow()
    ref_to_id: dict[str, uuid.UUID] = {}
    results: list[ConfirmedItem] = []
    created = linked = skipped = 0
    reviews_new = reviews_old = 0
    explanation_for_question: dict[uuid.UUID, uuid.UUID] = {}
    tested_for_question: dict[uuid.UUID, uuid.UUID] = {}
    ktype_of: dict[uuid.UUID, KnowledgeType] = {}

    for it in req.items:
        if it.action == "skip":
            results.append(ConfirmedItem(ref=it.ref, knowledge_id=None, outcome="skipped"))
            skipped += 1
            continue
        exp = _check_explanation(db, it.question_id, it.explanation_id)
        explanation_for_question[it.question_id] = exp.id
        details = dict(it.details)
        if it.action == "link":
            target = db.get(KnowledgeItem, it.target_knowledge_id)
            if (
                target is None
                or target.status != KnowledgeStatus.ACTIVE
                or target.knowledge_type != it.knowledge_type
            ):
                raise DomainValidationError(
                    "Mục kiến thức để gộp không hợp lệ.", details={"ref": it.ref}
                )
            knowledge, outcome = target, "linked"
        else:
            key = key_for(it.knowledge_type, it.title, details)
            existing = db.scalar(
                select(KnowledgeItem).where(
                    KnowledgeItem.knowledge_type == it.knowledge_type.value,
                    KnowledgeItem.canonical_key == key,
                    KnowledgeItem.status == KnowledgeStatus.ACTIVE.value,
                )
            )
            if it.action == "create" and existing is not None:
                knowledge, outcome = existing, "linked"  # repeat confirmation / same key in batch
            else:
                if it.action == "create_new_sense" and existing is not None:
                    key = _next_sense_key(db, it.knowledge_type, key)
                knowledge = KnowledgeItem(
                    knowledge_type=it.knowledge_type.value,
                    jlpt_level="N3",
                    title=it.title,
                    content=it.summary or details.get("meaning_vi") or "",
                    canonical_key=key,
                    details=details,
                    source_explanation_id=exp.id,
                )
                db.add(knowledge)
                db.flush()
                outcome = "created"
        ref_to_id[it.ref] = knowledge.id
        ktype_of[knowledge.id] = KnowledgeType(knowledge.knowledge_type)
        created += outcome == "created"
        linked += outcome == "linked"
        results.append(ConfirmedItem(ref=it.ref, knowledge_id=knowledge.id, outcome=outcome))

        link = db.get(QuestionKnowledge, (it.question_id, knowledge.id))
        if link is None:
            db.add(
                QuestionKnowledge(
                    question_id=it.question_id,
                    knowledge_id=knowledge.id,
                    relation_type=it.role.value,
                )
            )
        elif ROLE_RANK[it.role] > ROLE_RANK[KnowledgeRelation(link.relation_type)]:
            link.relation_type = it.role.value
        if not db.scalar(
            select(KnowledgeEvidence.id).where(
                KnowledgeEvidence.knowledge_id == knowledge.id,
                KnowledgeEvidence.question_id == it.question_id,
                KnowledgeEvidence.explanation_id == exp.id,
            )
        ):
            db.add(
                KnowledgeEvidence(
                    knowledge_id=knowledge.id,
                    question_id=it.question_id,
                    explanation_id=exp.id,
                    role=it.role.value,
                    extracted={"title": it.title, "summary": it.summary, "details": details},
                    confirmed_at=now,
                )
            )
        if it.role == KnowledgeRelation.TESTS:
            tested_for_question.setdefault(it.question_id, knowledge.id)
        db.flush()

        if (
            req.create_reviews
            and it.role != KnowledgeRelation.CONTEXT
            and ktype_of[knowledge.id] in RECALL_TYPES
        ):
            _, new = reviews.ensure_item(
                db,
                review_type=ReviewType.KNOWLEDGE_RECALL,
                dedup_key=f"k:{knowledge.id}",
                knowledge_id=knowledge.id,
                source_question_ids=[it.question_id],
                source_explanation_id=exp.id,
                now=now,
            )
            reviews_new += new
            reviews_old += not new

    relations_created = 0
    for rel in req.relations:
        a, b = ref_to_id.get(rel.source_ref), ref_to_id.get(rel.target_ref)
        if a is None or b is None:
            continue  # one side skipped
        if add_relation(db, a, b, rel.relation_type):
            relations_created += 1
        if (
            req.create_reviews
            and rel.relation_type == KnowledgeLink.CONFUSED_WITH
            and ktype_of[a] == ktype_of[b]
            and ktype_of[a] in {KnowledgeType.GRAMMAR, KnowledgeType.VOCABULARY}
        ):
            x, y = sorted([a, b], key=str)
            _, new = reviews.ensure_item(
                db,
                review_type=ReviewType.CONTRAST,
                dedup_key=reviews.contrast_key(a, b),
                knowledge_id=x,
                related_knowledge_id=y,
                now=now,
            )
            reviews_new += new
            reviews_old += not new

    if req.create_reviews:
        for qid, exp_id in explanation_for_question.items():
            if not _has_mistake(db, qid):
                continue  # Type A is for questions you actually got wrong
            _, new = reviews.ensure_item(
                db,
                review_type=ReviewType.ORIGINAL_QUESTION,
                dedup_key=f"q:{qid}",
                knowledge_id=tested_for_question.get(qid),
                source_question_id=qid,
                source_question_ids=[qid],
                source_explanation_id=exp_id,
                now=now,
            )
            reviews_new += new
            reviews_old += not new
    db.commit()
    return ConfirmResult(
        items=results,
        created=created,
        linked=linked,
        skipped=skipped,
        relations_created=relations_created,
        review_items_created=reviews_new,
        review_items_existing=reviews_old,
    )


# ------------------------------------------------------------------ reading
def _get(db: Session, knowledge_id: uuid.UUID) -> KnowledgeItem:
    k = db.get(KnowledgeItem, knowledge_id)
    if k is None:
        raise NotFoundError(
            "Không tìm thấy mục kiến thức.", details={"knowledge_id": str(knowledge_id)}
        )
    return k


def _question_counts(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    return dict(
        db.execute(  # type: ignore[arg-type]
            select(QuestionKnowledge.knowledge_id, func.count())
            .where(QuestionKnowledge.knowledge_id.in_(ids))
            .group_by(QuestionKnowledge.knowledge_id)
        ).all()
    )


def to_list_item(k: KnowledgeItem, stats: dict[str, Any], question_count: int) -> KnowledgeListItem:
    return KnowledgeListItem(
        id=k.id,
        knowledge_type=KnowledgeType(k.knowledge_type),
        title=k.title,
        content=k.content,
        canonical_key=k.canonical_key,
        status=KnowledgeStatus(k.status),
        question_count=question_count,
        stats=KnowledgeStats.model_validate(stats),
        created_at=k.created_at,
        updated_at=k.updated_at,
    )


def list_knowledge(
    db: Session,
    *,
    knowledge_type: KnowledgeType | None,
    status: str,
    q: str | None,
    priority: str | None,
) -> list[KnowledgeListItem]:
    from app.analytics.weakness import knowledge_stats

    stmt = select(KnowledgeItem)
    if status != "all":
        stmt = stmt.where(KnowledgeItem.status == status)
    if knowledge_type:
        stmt = stmt.where(KnowledgeItem.knowledge_type == knowledge_type.value)
    if q:
        like = f"%{q.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(
            or_(
                KnowledgeItem.title.ilike(like),
                KnowledgeItem.content.ilike(like),
                KnowledgeItem.canonical_key.ilike(like),
            )
        )
    items = list(db.scalars(stmt.order_by(KnowledgeItem.created_at.desc())))
    ids = [k.id for k in items]
    stats = knowledge_stats(db, ids)
    qcounts = _question_counts(db, ids)
    out = [to_list_item(k, stats[k.id], qcounts.get(k.id, 0)) for k in items]
    if priority:
        out = [o for o in out if o.stats.priority == priority]
    order = {"review_now": 0, "due_soon": 1, "stable": 2, "insufficient_data": 3}
    return sorted(out, key=lambda o: (order[o.stats.priority], -(o.stats.incorrect)))


def detail(db: Session, knowledge_id: uuid.UUID) -> KnowledgeDetail:
    from app.analytics.weakness import knowledge_stats

    k = _get(db, knowledge_id)
    stats = knowledge_stats(db, [k.id])[k.id]
    questions: list[LinkedQuestion] = []
    for link, q, exam in db.execute(
        select(QuestionKnowledge, Question, Exam)
        .join(Question, Question.id == QuestionKnowledge.question_id)
        .join(Exam, Exam.id == Question.exam_id)
        .where(QuestionKnowledge.knowledge_id == k.id)
        .order_by(Exam.title, Question.question_number)
    ):
        mistakes = [
            {
                "attempt_id": str(att.id),
                "attempt_answer_id": str(a.id),
                "selected_answer": a.selected_answer,
                "started_at": att.started_at.isoformat(),
            }
            for a, att in db.execute(
                select(AttemptAnswer, ExamAttempt)
                .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
                .where(AttemptAnswer.question_id == q.id, AttemptAnswer.is_correct.is_(False))
                .order_by(ExamAttempt.started_at.desc())
            )
        ]
        questions.append(
            LinkedQuestion(
                question_id=q.id,
                exam_id=exam.id,
                exam_title=exam.title,
                question_number=q.question_number,
                question_text=q.question_text,
                role=KnowledgeRelation(link.relation_type),
                mistakes=mistakes,
            )
        )
    related: list[RelatedItem] = []
    for rel in db.scalars(
        select(KnowledgeRelationLink).where(
            or_(KnowledgeRelationLink.source_id == k.id, KnowledgeRelationLink.target_id == k.id)
        )
    ):
        other_id = rel.target_id if rel.source_id == k.id else rel.source_id
        other = db.get(KnowledgeItem, other_id)
        if other is None:
            continue
        rtype = KnowledgeLink(rel.relation_type)
        direction = (
            "symmetric"
            if rtype in SYMMETRIC
            else ("outgoing" if rel.source_id == k.id else "incoming")
        )
        related.append(
            RelatedItem(
                knowledge_id=other.id,
                title=other.title,
                knowledge_type=KnowledgeType(other.knowledge_type),
                relation_type=rtype,
                direction=direction,
            )
        )
    evidence: list[EvidenceRead] = []
    for ev in db.scalars(
        select(KnowledgeEvidence)
        .where(KnowledgeEvidence.knowledge_id == k.id)
        .order_by(KnowledgeEvidence.confirmed_at)
    ):
        exp = db.get(AIExplanation, ev.explanation_id) if ev.explanation_id else None
        q = db.get(Question, ev.question_id) if ev.question_id else None
        evidence.append(
            EvidenceRead(
                question_id=ev.question_id,
                explanation_id=ev.explanation_id,
                explanation_status=VerificationStatus(exp.verification_status) if exp else None,
                explanation_stale=(exp.content_hash != current_content_hash(db, q))
                if exp and q
                else None,
                role=KnowledgeRelation(ev.role),
                extracted=ev.extracted,
                confirmed_at=ev.confirmed_at,
            )
        )
    review_items = [
        ReviewItemBrief.model_validate(r)
        for r in db.scalars(
            select(ReviewItem).where(
                or_(ReviewItem.knowledge_id == k.id, ReviewItem.related_knowledge_id == k.id)
            )
        )
    ]
    base = to_list_item(k, stats, len(questions))
    return KnowledgeDetail(
        **base.model_dump(),
        details=k.details,
        merged_into_id=k.merged_into_id,
        source_explanation_id=k.source_explanation_id,
        version=k.version,
        questions=questions,
        related=related,
        evidence=evidence,
        review_items=review_items,
    )


# ------------------------------------------------------------------ edits
def update_knowledge(
    db: Session, knowledge_id: uuid.UUID, data: KnowledgeUpdate
) -> KnowledgeDetail:
    k = db.scalar(select(KnowledgeItem).where(KnowledgeItem.id == knowledge_id).with_for_update())
    if k is None:
        raise NotFoundError("Không tìm thấy mục kiến thức.")
    if k.version != data.version:
        raise ConflictError(
            "Mục kiến thức đã thay đổi; hãy tải lại.", details={"current_version": k.version}
        )
    if k.status == KnowledgeStatus.MERGED:
        raise ConflictError(
            "Mục đã được gộp vào mục khác.", details={"merged_into_id": str(k.merged_into_id)}
        )
    if data.title is not None:
        k.title = data.title  # display label only; the canonical key stays stable
    if data.content is not None:
        k.content = data.content
    if data.details is not None:
        k.details = data.details
    if data.status is not None:
        if data.status == "active" and k.status != "active":
            clash = db.scalar(
                select(KnowledgeItem.id).where(
                    KnowledgeItem.knowledge_type == k.knowledge_type,
                    KnowledgeItem.canonical_key == k.canonical_key,
                    KnowledgeItem.status == "active",
                )
            )
            if clash:
                raise ConflictError(
                    "Đã có mục đang hoạt động với cùng khoá; hãy gộp thay vì khôi phục."
                )
        k.status = data.status
    k.version += 1
    db.commit()
    return detail(db, k.id)


def merge(db: Session, target_id: uuid.UUID, source_ids: list[uuid.UUID]) -> KnowledgeDetail:
    target = db.scalar(select(KnowledgeItem).where(KnowledgeItem.id == target_id).with_for_update())
    if target is None or target.status != KnowledgeStatus.ACTIVE:
        raise DomainValidationError("Mục đích để gộp phải đang hoạt động.")
    for sid in dict.fromkeys(source_ids):
        if sid == target_id:
            raise DomainValidationError("Không thể gộp một mục vào chính nó.")
        src = db.scalar(select(KnowledgeItem).where(KnowledgeItem.id == sid).with_for_update())
        if src is None or src.status == KnowledgeStatus.MERGED:
            raise DomainValidationError(
                "Mục nguồn không hợp lệ.", details={"knowledge_id": str(sid)}
            )
        if src.knowledge_type != target.knowledge_type:
            raise DomainValidationError("Chỉ gộp được các mục cùng loại.")
        for link in db.scalars(
            select(QuestionKnowledge).where(QuestionKnowledge.knowledge_id == sid)
        ):
            existing = db.get(QuestionKnowledge, (link.question_id, target_id))
            if existing is None:
                db.add(
                    QuestionKnowledge(
                        question_id=link.question_id,
                        knowledge_id=target_id,
                        relation_type=link.relation_type,
                    )
                )
            elif (
                ROLE_RANK[KnowledgeRelation(link.relation_type)]
                > ROLE_RANK[KnowledgeRelation(existing.relation_type)]
            ):
                existing.relation_type = link.relation_type
        db.execute(delete(QuestionKnowledge).where(QuestionKnowledge.knowledge_id == sid))
        for ev in db.scalars(
            select(KnowledgeEvidence).where(KnowledgeEvidence.knowledge_id == sid)
        ):
            dup = db.scalar(
                select(KnowledgeEvidence.id).where(
                    KnowledgeEvidence.knowledge_id == target_id,
                    KnowledgeEvidence.question_id == ev.question_id,
                    KnowledgeEvidence.explanation_id == ev.explanation_id,
                )
            )
            if dup:
                db.delete(ev)
            else:
                ev.knowledge_id = target_id
        for rel in list(
            db.scalars(
                select(KnowledgeRelationLink).where(
                    or_(
                        KnowledgeRelationLink.source_id == sid,
                        KnowledgeRelationLink.target_id == sid,
                    )
                )
            )
        ):
            a = target_id if rel.source_id == sid else rel.source_id
            b = target_id if rel.target_id == sid else rel.target_id
            rtype = KnowledgeLink(rel.relation_type)
            db.delete(rel)
            db.flush()
            add_relation(db, a, b, rtype, rel.source_explanation_id)
        reviews.repoint_knowledge(db, sid, target_id)
        from app.practice.models import GeneratedPracticeQuestion

        db.execute(
            update(GeneratedPracticeQuestion)
            .where(GeneratedPracticeQuestion.knowledge_id == sid)
            .values(knowledge_id=target_id)
        )
        src.status = KnowledgeStatus.MERGED.value
        src.merged_into_id = target_id
        src.version += 1
        db.flush()
    target.version += 1
    db.commit()
    return detail(db, target_id)


def split(
    db: Session, knowledge_id: uuid.UUID, title: str, content: str, question_ids: list[uuid.UUID]
) -> KnowledgeDetail:
    src = db.scalar(select(KnowledgeItem).where(KnowledgeItem.id == knowledge_id).with_for_update())
    if src is None or src.status != KnowledgeStatus.ACTIVE:
        raise DomainValidationError("Chỉ tách được mục đang hoạt động.")
    linked = set(
        db.scalars(
            select(QuestionKnowledge.question_id).where(
                QuestionKnowledge.knowledge_id == knowledge_id
            )
        )
    )
    move = set(question_ids)
    if not move <= linked:
        raise DomainValidationError("Một số câu không liên kết với mục này.")
    if move == linked:
        raise DomainValidationError("Phải giữ lại ít nhất một câu ở mục gốc.")
    ktype = KnowledgeType(src.knowledge_type)
    new = KnowledgeItem(
        knowledge_type=ktype.value,
        jlpt_level=src.jlpt_level,
        title=title,
        content=content or src.content,
        canonical_key=_next_sense_key(db, ktype, src.canonical_key),
        details=dict(src.details),
        source_explanation_id=src.source_explanation_id,
    )
    db.add(new)
    db.flush()
    db.execute(
        update(QuestionKnowledge)
        .where(
            QuestionKnowledge.knowledge_id == knowledge_id, QuestionKnowledge.question_id.in_(move)
        )
        .values(knowledge_id=new.id)
    )
    db.execute(
        update(KnowledgeEvidence)
        .where(
            KnowledgeEvidence.knowledge_id == knowledge_id, KnowledgeEvidence.question_id.in_(move)
        )
        .values(knowledge_id=new.id)
    )
    has_recall = db.scalar(select(ReviewItem.id).where(ReviewItem.dedup_key == f"k:{knowledge_id}"))
    if has_recall and ktype in RECALL_TYPES:
        reviews.ensure_item(
            db,
            review_type=ReviewType.KNOWLEDGE_RECALL,
            dedup_key=f"k:{new.id}",
            knowledge_id=new.id,
            source_question_ids=list(move),
        )
    db.execute(
        update(ReviewItem)
        .where(
            ReviewItem.review_type == ReviewType.ORIGINAL_QUESTION.value,
            ReviewItem.source_question_id.in_(move),
            ReviewItem.knowledge_id == knowledge_id,
        )
        .values(knowledge_id=new.id)
    )
    src.version += 1
    db.commit()
    return detail(db, new.id)


def create_relation(
    db: Session, source_id: uuid.UUID, target_id: uuid.UUID, rel: KnowledgeLink
) -> KnowledgeDetail:
    a, b = _get(db, source_id), _get(db, target_id)
    if a.status != KnowledgeStatus.ACTIVE or b.status != KnowledgeStatus.ACTIVE:
        raise DomainValidationError("Chỉ liên kết các mục đang hoạt động.")
    if not add_relation(db, a.id, b.id, rel):
        raise ConflictError("Liên kết đã tồn tại hoặc không hợp lệ.")
    db.commit()
    return detail(db, source_id)


def extract(
    db: Session, question_ids: list[uuid.UUID] | None, attempt_id: uuid.UUID | None
) -> list[extraction.QuestionExtraction]:
    if attempt_id is not None:
        rows = explanations.attempt_answers(db, attempt_id)
        question_ids = [q.id for a, q in rows if a.is_correct is False]
    return [extraction.extract_for_question(db, qid) for qid in dict.fromkeys(question_ids or [])]
