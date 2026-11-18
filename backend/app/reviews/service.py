"""Review items, sessions and events.

Card kinds (all built from verified / approved data only — never from unreviewed AI output):
* ``question``       Type A — the original question; graded against its *verified* key
* ``practice``       Type B — an AI practice question the user approved
* ``meaning_choice`` Type B — "what does 〜ので mean?" with glosses of your other items
* ``reading_choice`` Type B — kanji word reading vs the confusable readings of the source question
* ``contrast``       Type C — approved example with the pattern blanked, or meaning → pattern
* ``self_check``     fallback when nothing gradable can be built (reveal + self-rating)

Answering a card only reveals the result; *only a rating event* changes the schedule.
"""

import copy
import hashlib
import random
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.database.enums import (
    KnowledgeStatus,
    PracticeStatus,
    ReviewItemStatus,
    ReviewRating,
    ReviewType,
    SrsState,
)
from app.exams.models import Passage, Question
from app.explanations import service as explanations
from app.explanations.context import Ineligible, build_context
from app.explanations.payload import ExplanationPayload
from app.knowledge import normalize as nz
from app.knowledge.models import KnowledgeItem
from app.practice.models import GeneratedPracticeQuestion
from app.reviews import srs
from app.reviews.models import ReviewEvent, ReviewItem, ReviewSession

CLOCK_SKEW = timedelta(minutes=5)
MAX_SESSION_CARDS = 50


# ------------------------------------------------------------------ items
def ensure_item(
    db: Session,
    *,
    review_type: ReviewType,
    dedup_key: str,
    knowledge_id: uuid.UUID | None = None,
    related_knowledge_id: uuid.UUID | None = None,
    source_question_id: uuid.UUID | None = None,
    source_question_ids: list[uuid.UUID] | None = None,
    source_explanation_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> tuple[ReviewItem, bool]:
    """Idempotent: an existing item with the same dedup_key is returned (sources merged)."""
    existing = db.scalar(select(ReviewItem).where(ReviewItem.dedup_key == dedup_key))
    sources = [str(q) for q in (source_question_ids or [])]
    if existing is not None:
        merged = list(dict.fromkeys([*existing.source_question_ids, *sources]))
        if merged != existing.source_question_ids:
            existing.source_question_ids = merged
        return existing, False
    item = ReviewItem(
        review_type=review_type.value,
        dedup_key=dedup_key,
        knowledge_id=knowledge_id,
        related_knowledge_id=related_knowledge_id,
        source_question_id=source_question_id,
        source_question_ids=sources,
        source_explanation_id=source_explanation_id,
        srs_state=SrsState.NEW.value,
        step_index=None,
        due_at=now or utcnow(),  # new items are due immediately
        algorithm_version=srs.ALGORITHM_VERSION,
        ladder=srs.DEFAULT_LADDER,
    )
    db.add(item)
    db.flush()
    return item, True


def contrast_key(a: uuid.UUID, b: uuid.UUID) -> str:
    x, y = sorted([str(a), str(b)])
    return f"c:{x}:{y}"


def snapshot(item: ReviewItem) -> srs.SrsSnapshot:
    return srs.SrsSnapshot(
        state=SrsState(item.srs_state),
        step_index=item.step_index,
        interval_minutes=item.interval_minutes,
        due_at=item.due_at,
        last_reviewed_at=item.last_reviewed_at,
        review_count=item.review_count,
        lapse_count=item.lapse_count,
    )


def blocked_reason(db: Session, item: ReviewItem) -> str | None:
    """Why an item cannot be presented right now (source no longer verified/approved)."""
    if item.review_type == ReviewType.ORIGINAL_QUESTION:
        if item.source_question_id is None:
            return "question_deleted"
        ctx = build_context(db, item.source_question_id)
        if isinstance(ctx, Ineligible):
            return ctx.code
        return None
    for kid in (item.knowledge_id, item.related_knowledge_id):
        if kid is None:
            continue
        k = db.get(KnowledgeItem, kid)
        if k is None or k.status != KnowledgeStatus.ACTIVE:
            return "knowledge_inactive"
    return None


def item_label(db: Session, item: ReviewItem) -> str:
    if item.review_type == ReviewType.ORIGINAL_QUESTION and item.source_question_id:
        q = db.get(Question, item.source_question_id)
        return (
            f"Câu {q.question_number}: {nz.clean(q.question_text)[:40]}" if q else "Câu hỏi đã xoá"
        )
    k = db.get(KnowledgeItem, item.knowledge_id) if item.knowledge_id else None
    r = db.get(KnowledgeItem, item.related_knowledge_id) if item.related_knowledge_id else None
    if item.review_type == ReviewType.CONTRAST and k and r:
        return f"{k.title} ⇄ {r.title}"
    return k.title if k else "—"


def list_items(
    db: Session, bucket: str, now: datetime | None = None
) -> list[tuple[ReviewItem, str | None]]:
    now = now or utcnow()
    base = select(ReviewItem)
    if bucket == "due":
        stmt = base.where(
            ReviewItem.status == ReviewItemStatus.ACTIVE.value, ReviewItem.due_at <= now
        ).order_by(ReviewItem.due_at)
    elif bucket == "upcoming":
        stmt = base.where(
            ReviewItem.status == ReviewItemStatus.ACTIVE.value,
            ReviewItem.due_at > now,
            ReviewItem.due_at <= now + timedelta(days=7),
        ).order_by(ReviewItem.due_at)
    elif bucket == "completed":
        stmt = base.where(ReviewItem.review_count > 0).order_by(ReviewItem.last_reviewed_at.desc())
    elif bucket == "suspended":
        stmt = base.where(ReviewItem.status != ReviewItemStatus.ACTIVE.value).order_by(
            ReviewItem.updated_at.desc()
        )
    else:  # insufficient: active items whose source can no longer be presented
        stmt = base.where(ReviewItem.status == ReviewItemStatus.ACTIVE.value).order_by(
            ReviewItem.created_at
        )
    items = list(db.scalars(stmt))
    out = [(i, blocked_reason(db, i)) for i in items]
    if bucket == "insufficient":
        return [(i, r) for i, r in out if r is not None]
    if bucket in {"due", "upcoming"}:
        return [(i, r) for i, r in out if r is None]
    return out


def counts(db: Session, now: datetime | None = None) -> dict[str, int]:
    return {
        b: len(list_items(db, b, now))
        for b in ("due", "upcoming", "completed", "insufficient", "suspended")
    }


def set_status(
    db: Session, item_id: uuid.UUID, status: ReviewItemStatus, version: int
) -> ReviewItem:
    item = db.scalar(select(ReviewItem).where(ReviewItem.id == item_id).with_for_update())
    if item is None:
        raise NotFoundError("Không tìm thấy mục ôn tập.")
    if item.version != version:
        raise ConflictError(
            "Mục ôn tập đã thay đổi; hãy tải lại.", details={"current_version": item.version}
        )
    item.status = status.value
    item.version += 1
    db.commit()
    return item


# ------------------------------------------------------------------ cards
def _shuffle(options: list[str], answer: int, seed: str) -> tuple[list[str], int]:
    order = list(range(len(options)))
    random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16)).shuffle(order)
    return [options[i] for i in order], order.index(answer)


def _question_card(db: Session, item: ReviewItem) -> dict[str, Any] | None:
    assert item.source_question_id is not None
    ctx = build_context(db, item.source_question_id)
    if isinstance(ctx, Ineligible):
        return None
    q = db.get(Question, item.source_question_id)
    assert q is not None
    passage = db.get(Passage, q.passage_id) if q.passage_id else None
    return {
        "kind": "question",
        "prompt": q.question_text,
        "passage": passage.content if passage else None,
        "options": list(q.options),
        "answer_index": ctx.correct_index,
        "question_id": str(q.id),
    }


def _practice_card(db: Session, knowledge: KnowledgeItem) -> dict[str, Any] | None:
    practice = db.scalar(
        select(GeneratedPracticeQuestion)
        .where(
            GeneratedPracticeQuestion.knowledge_id == knowledge.id,
            GeneratedPracticeQuestion.status == PracticeStatus.APPROVED.value,
        )
        .order_by(GeneratedPracticeQuestion.times_used, GeneratedPracticeQuestion.created_at)
        .limit(1)
    )
    if practice is None:
        return None
    practice.times_used += 1
    return {
        "kind": "practice",
        "prompt": practice.question_text,
        "passage": None,
        "options": list(practice.options),
        "answer_index": practice.answer_index,
        "practice_id": str(practice.id),
    }


def _gloss(k: KnowledgeItem) -> str:
    return (k.details.get("meaning_vi") or k.content or "").strip()


def _recall_card(
    db: Session, item: ReviewItem, knowledge: KnowledgeItem, seed: str
) -> dict[str, Any]:
    practice = _practice_card(db, knowledge)
    if practice is not None:
        return practice
    if knowledge.knowledge_type == "kanji":
        confusions = [
            nz.clean(c.get("option", "")) for c in knowledge.details.get("confusions", [])
        ]
        confusions = [
            c for c in dict.fromkeys(confusions) if c and c != knowledge.details.get("reading")
        ]
        reading = knowledge.details.get("reading")
        word = knowledge.details.get("word")
        if reading and word and confusions:
            options, answer = _shuffle([reading, *confusions[:3]], 0, seed)
            return {
                "kind": "reading_choice",
                "prompt": f"Cách đọc đúng của「{word}」là gì?",
                "options": options,
                "answer_index": answer,
                "passage": None,
            }
    gloss = _gloss(knowledge)
    others = db.scalars(
        select(KnowledgeItem).where(
            KnowledgeItem.knowledge_type == knowledge.knowledge_type,
            KnowledgeItem.status == KnowledgeStatus.ACTIVE.value,
            KnowledgeItem.id != knowledge.id,
        )
    ).all()
    distractors = [g for g in dict.fromkeys(_gloss(o) for o in others) if g and g != gloss]
    if gloss and distractors:
        rng = random.Random(seed)
        picked = rng.sample(distractors, min(3, len(distractors)))
        options, answer = _shuffle([gloss, *picked], 0, seed)
        return {
            "kind": "meaning_choice",
            "prompt": f"「{knowledge.title}」nghĩa là gì?",
            "options": options,
            "answer_index": answer,
            "passage": None,
        }
    return {
        "kind": "self_check",
        "prompt": f"Bạn có nhớ「{knowledge.title}」nghĩa là gì và dùng thế nào không?",
        "options": [],
        "answer_index": None,
        "passage": None,
    }


def _contrast_card(
    item: ReviewItem, a: KnowledgeItem, b: KnowledgeItem, seed: str
) -> dict[str, Any]:
    for target, other in ((a, b), (b, a)):
        core = target.details.get("core") or nz.grammar_core(target.title)
        for example in target.details.get("examples", []) or []:
            if core and core in example:
                blanked = example.replace(core, "（　　）", 1)
                options, answer = _shuffle([target.title, other.title], 0, seed)
                return {
                    "kind": "contrast",
                    "prompt": f"Chọn mẫu phù hợp: {blanked}",
                    "options": options,
                    "answer_index": answer,
                    "passage": None,
                }
    if _gloss(a) and _gloss(b) and _gloss(a) != _gloss(b):
        options, answer = _shuffle([a.title, b.title], 0, seed)
        return {
            "kind": "contrast",
            "prompt": f"Mẫu nào mang nghĩa “{_gloss(a)}”?",
            "options": options,
            "answer_index": answer,
            "passage": None,
        }
    return {
        "kind": "self_check",
        "prompt": f"Phân biệt「{a.title}」và「{b.title}」.",
        "options": [],
        "answer_index": None,
        "passage": None,
    }


def build_card(db: Session, item: ReviewItem, seed: str) -> dict[str, Any] | None:
    if item.review_type == ReviewType.ORIGINAL_QUESTION:
        card = _question_card(db, item)
    elif item.review_type == ReviewType.KNOWLEDGE_RECALL:
        k = db.get(KnowledgeItem, item.knowledge_id) if item.knowledge_id else None
        card = _recall_card(db, item, k, seed) if k and k.status == KnowledgeStatus.ACTIVE else None
    else:
        a = db.get(KnowledgeItem, item.knowledge_id) if item.knowledge_id else None
        b = db.get(KnowledgeItem, item.related_knowledge_id) if item.related_knowledge_id else None
        ok = a and b and a.status == KnowledgeStatus.ACTIVE and b.status == KnowledgeStatus.ACTIVE
        card = _contrast_card(item, a, b, seed) if ok else None  # type: ignore[arg-type]
    if card is None:
        return None
    card.update(
        card_id=uuid.uuid4().hex[:12],
        review_item_id=str(item.id),
        review_type=item.review_type,
        label=item_label(db, item),
        answered=False,
        selected_index=None,
        correct=None,
        rated=False,
    )
    return card


def public_card(card: dict[str, Any]) -> dict[str, Any]:
    hidden = {"answer_index"} if not card.get("answered") else set()
    return {k: v for k, v in card.items() if k not in hidden}


def create_session(db: Session, limit: int, now: datetime | None = None) -> ReviewSession:
    now = now or utcnow()
    session_id = uuid.uuid4()
    cards: list[dict[str, Any]] = []
    for item, reason in list_items(db, "due", now):
        if reason is not None:
            continue
        card = build_card(db, item, seed=f"{session_id}:{item.id}")
        if card is not None:
            cards.append(card)
        if len(cards) >= min(limit, MAX_SESSION_CARDS):
            break
    session = ReviewSession(id=session_id, cards=cards)
    db.add(session)
    db.commit()
    return session


def get_session(db: Session, session_id: uuid.UUID) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if session is None:
        raise NotFoundError("Không tìm thấy phiên ôn tập.")
    return session


def _find_card(session: ReviewSession, card_id: str) -> tuple[int, dict[str, Any]]:
    return _find_card_in(session.cards, card_id)


def _find_card_in(cards: list[dict[str, Any]], card_id: str) -> tuple[int, dict[str, Any]]:
    for i, card in enumerate(cards):
        if card["card_id"] == card_id:
            return i, card
    raise NotFoundError("Không tìm thấy thẻ trong phiên.", details={"card_id": card_id})


def reveal(db: Session, card: dict[str, Any]) -> dict[str, Any]:
    """Explanation shown after answering (approved explanation / approved practice / item)."""
    if card["kind"] == "question":
        qid = uuid.UUID(card["question_id"])
        ctx = build_context(db, qid)
        if isinstance(ctx, Ineligible):
            return {"type": "none"}
        current = explanations.find_current(db, qid, ctx.content_hash)
        if current is not None and current.verification_status == "approved":
            return {
                "type": "explanation",
                "explanation_id": str(current.id),
                "payload": ExplanationPayload.model_validate(current.explanation_json).model_dump(),
            }
        return {"type": "none", "message": "Chưa có lời giải đã duyệt cho câu này."}
    if card["kind"] == "practice":
        p = db.get(GeneratedPracticeQuestion, uuid.UUID(card["practice_id"]))
        return {"type": "practice", "payload": p.payload if p else None}
    item = db.get(ReviewItem, uuid.UUID(card["review_item_id"]))
    out: list[dict[str, Any]] = []
    for kid in (item.knowledge_id, item.related_knowledge_id) if item else ():
        if kid:
            k = db.get(KnowledgeItem, kid)
            if k:
                out.append(
                    {
                        "knowledge_id": str(k.id),
                        "title": k.title,
                        "content": k.content,
                        "details": k.details,
                    }
                )
    return {"type": "knowledge", "items": out}


def answer_card(
    db: Session, session_id: uuid.UUID, card_id: str, selected: int | None
) -> dict[str, Any]:
    session = db.scalar(
        select(ReviewSession).where(ReviewSession.id == session_id).with_for_update()
    )
    if session is None:
        raise NotFoundError("Không tìm thấy phiên ôn tập.")
    cards = copy.deepcopy(session.cards)  # JSONB: assign a new value so the change is saved
    _, card = _find_card_in(cards, card_id)
    if card["answered"]:
        return {"card": public_card(card), "reveal": reveal(db, card)}
    if card["answer_index"] is not None:
        if selected is not None and not 0 <= selected < len(card["options"]):
            raise DomainValidationError("Lựa chọn không hợp lệ.")
        card["correct"] = None if selected is None else selected == card["answer_index"]
    card["answered"], card["selected_index"] = True, selected
    session.cards = cards
    db.commit()
    return {"card": public_card(card), "reveal": reveal(db, card)}


# ------------------------------------------------------------------ events
def record_event(
    db: Session,
    *,
    request_id: uuid.UUID,
    review_item_id: uuid.UUID,
    rating: ReviewRating,
    timezone: str,
    session_id: uuid.UUID | None,
    card_id: str | None,
    reviewed_at: datetime | None,
) -> tuple[ReviewEvent, bool]:
    existing = db.scalar(select(ReviewEvent).where(ReviewEvent.request_id == request_id))
    if existing is not None:
        if existing.review_item_id != review_item_id:
            raise ConflictError("request_id đã được dùng cho mục ôn khác.")
        return existing, False
    try:
        zone = srs.resolve_zone(timezone)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc
    now = utcnow()
    at = reviewed_at or now
    if at > now + CLOCK_SKEW:
        raise DomainValidationError("Thời điểm ôn không được ở tương lai.")
    item = db.scalar(select(ReviewItem).where(ReviewItem.id == review_item_id).with_for_update())
    if item is None:
        raise NotFoundError("Không tìm thấy mục ôn tập.")
    if item.status != ReviewItemStatus.ACTIVE:
        raise ConflictError("Mục ôn tập đang tạm dừng hoặc đã lưu trữ.")

    card: dict[str, Any] | None = None
    session: ReviewSession | None = None
    if session_id is not None and card_id is not None:
        session = db.scalar(
            select(ReviewSession).where(ReviewSession.id == session_id).with_for_update()
        )
        if session is None:
            raise NotFoundError("Không tìm thấy phiên ôn tập.")
        cards_copy = copy.deepcopy(session.cards)
        _, card = _find_card_in(cards_copy, card_id)
        if card["review_item_id"] != str(item.id):
            raise DomainValidationError("Thẻ không thuộc mục ôn này.")
        if card["answer_index"] is not None and not card["answered"]:
            raise DomainValidationError("Hãy trả lời thẻ trước khi đánh giá mức độ nhớ.")

    before = snapshot(item)
    ladder = srs.Ladder.parse(item.ladder)
    after = srs.schedule(before, rating, at, zone, ladder)
    event = ReviewEvent(
        review_item_id=item.id,
        rating=rating.value,
        reviewed_at=at,
        request_id=request_id,
        session_id=session_id,
        card_kind=card["kind"] if card else None,
        selected_answer_index=card["selected_index"] if card else None,
        answer_correct=card["correct"] if card else None,
        previous_state=before.as_json(),
        next_state=after.as_json(),
        next_due_at=after.due_at,
        algorithm_version=srs.ALGORITHM_VERSION,
        timezone=timezone,
    )
    db.add(event)
    item.srs_state = after.state.value
    item.step_index = after.step_index
    item.interval_minutes = after.interval_minutes
    item.due_at = after.due_at
    item.last_reviewed_at = after.last_reviewed_at
    item.review_count = after.review_count
    item.lapse_count = after.lapse_count
    item.version += 1
    if session is not None and card is not None:
        card["rated"] = True
        session.cards = cards_copy
        if all(c["rated"] for c in cards_copy):
            session.finished_at = now
    db.commit()
    return event, True


def history(
    db: Session, *, review_item_id: uuid.UUID | None, knowledge_id: uuid.UUID | None, limit: int
) -> list[tuple[ReviewEvent, ReviewItem]]:
    stmt = select(ReviewEvent, ReviewItem).join(
        ReviewItem, ReviewItem.id == ReviewEvent.review_item_id
    )
    if review_item_id:
        stmt = stmt.where(ReviewEvent.review_item_id == review_item_id)
    if knowledge_id:
        stmt = stmt.where(
            (ReviewItem.knowledge_id == knowledge_id)
            | (ReviewItem.related_knowledge_id == knowledge_id)
        )
    return [
        (e, i)
        for e, i in db.execute(stmt.order_by(ReviewEvent.reviewed_at.desc()).limit(limit)).all()
    ]


def repoint_knowledge(db: Session, source: uuid.UUID, target: uuid.UUID) -> None:
    """Used by merge: move review items of `source` to `target`, archiving duplicates."""
    for item in db.scalars(
        select(ReviewItem).where(
            (ReviewItem.knowledge_id == source) | (ReviewItem.related_knowledge_id == source)
        )
    ):
        if item.review_type == ReviewType.ORIGINAL_QUESTION:
            item.knowledge_id = target if item.knowledge_id == source else item.knowledge_id
            continue
        a = target if item.knowledge_id == source else item.knowledge_id
        b = target if item.related_knowledge_id == source else item.related_knowledge_id
        if item.review_type == ReviewType.KNOWLEDGE_RECALL:
            new_key = f"k:{a}"
        elif a == b or a is None or b is None:
            item.status = ReviewItemStatus.DONE.value
            continue
        else:
            new_key = contrast_key(a, b)
        clash = db.scalar(
            select(ReviewItem.id).where(ReviewItem.dedup_key == new_key, ReviewItem.id != item.id)
        )
        if clash is not None:
            item.status = ReviewItemStatus.DONE.value  # keep its history, stop scheduling it
            item.dedup_key = f"merged:{item.id}"
        else:
            if item.review_type == ReviewType.CONTRAST:
                x, y = sorted([a, b], key=str)
                a, b = x, y
            item.knowledge_id, item.related_knowledge_id, item.dedup_key = a, b, new_key
    db.flush()


def due_count(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    return int(
        db.scalar(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.status == ReviewItemStatus.ACTIVE.value, ReviewItem.due_at <= now
            )
        )
        or 0
    )


__all__ = ["re", "update"]
