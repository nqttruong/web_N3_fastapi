"""Weakness analytics from real attempt answers and review events.

Outcomes of an attempt answer are kept apart:
* correct / incorrect — answered, graded against a verified key
* unanswered          — left blank (NOT counted as wrong)
* ungraded            — answered but no verified key at the time (excluded from rates)
* never attempted     — linked questions with no attempt answer at all

Error rate = incorrect / (correct + incorrect) with a 95 % Wilson interval. With fewer than
``MIN_OBSERVATIONS`` graded answers an item is "insufficient_data", never "weak".
"""

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.core.time import utcnow
from app.database.enums import KnowledgeRelation, ReviewItemStatus
from app.exams.models import Question
from app.explanations.context import category_for
from app.knowledge.models import QuestionKnowledge
from app.reviews.models import ReviewEvent, ReviewItem

MIN_OBSERVATIONS = 3
WEAK_LOWER_BOUND = 0.3  # lower Wilson bound above this = clearly weak
DUE_SOON = timedelta(days=3)
COUNTED_ROLES = (KnowledgeRelation.TESTS.value, KnowledgeRelation.DISTRACTOR.value)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None, float | None]:
    if n == 0:
        return None, None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(p, 4), round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def confidence(n: int) -> str:
    if n == 0:
        return "none"
    if n < MIN_OBSERVATIONS:
        return "low"
    if n < 10:
        return "medium"
    return "high"


@dataclass
class _Counts:
    correct: int = 0
    incorrect: int = 0
    unanswered: int = 0
    ungraded: int = 0
    recent_incorrect: int = 0
    last_incorrect_at: datetime | None = None

    def add(
        self, selected: int | None, is_correct: bool | None, at: datetime, recent_from: datetime
    ) -> None:
        if selected is None:
            self.unanswered += 1
        elif is_correct is None:
            self.ungraded += 1
        elif is_correct:
            self.correct += 1
        else:
            self.incorrect += 1
            if at >= recent_from:
                self.recent_incorrect += 1
            if self.last_incorrect_at is None or at > self.last_incorrect_at:
                self.last_incorrect_at = at

    @property
    def graded(self) -> int:
        return self.correct + self.incorrect

    def summary(self) -> dict[str, Any]:
        rate, low, high = wilson(self.incorrect, self.graded)
        return {
            "encounters": self.correct + self.incorrect + self.unanswered + self.ungraded,
            "correct": self.correct,
            "incorrect": self.incorrect,
            "unanswered": self.unanswered,
            "ungraded": self.ungraded,
            "error_rate": rate,
            "error_rate_low": low,
            "error_rate_high": high,
            "confidence": confidence(self.graded),
            "recent_incorrect_7d": self.recent_incorrect,
            "last_incorrect_at": self.last_incorrect_at,
        }


def _window_start(window: str, now: datetime) -> datetime | None:
    return {"7d": now - timedelta(days=7), "30d": now - timedelta(days=30)}.get(window)


def priority(stats: dict[str, Any], now: datetime) -> str:
    due = stats.get("next_due_at")
    graded = stats["correct"] + stats["incorrect"]
    if due is not None and due <= now:
        return "review_now"
    if (
        graded >= MIN_OBSERVATIONS
        and (stats["error_rate_low"] or 0) >= WEAK_LOWER_BOUND
        and stats["recent_incorrect_7d"]
    ):
        return "review_now"
    if due is not None and due <= now + DUE_SOON:
        return "due_soon"
    if graded < MIN_OBSERVATIONS and not stats["review_events"]:
        return "insufficient_data"
    return "stable"


def knowledge_stats(
    db: Session, knowledge_ids: list[uuid.UUID], *, window: str = "all", now: datetime | None = None
) -> dict[uuid.UUID, dict[str, Any]]:
    now = now or utcnow()
    start = _window_start(window, now)
    recent_from = now - timedelta(days=7)
    counts: dict[uuid.UUID, _Counts] = defaultdict(_Counts)
    if not knowledge_ids:
        return {}
    stmt = (
        select(
            QuestionKnowledge.knowledge_id,
            AttemptAnswer.selected_answer,
            AttemptAnswer.is_correct,
            ExamAttempt.started_at,
        )
        .join(AttemptAnswer, AttemptAnswer.question_id == QuestionKnowledge.question_id)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .where(
            QuestionKnowledge.knowledge_id.in_(knowledge_ids),
            QuestionKnowledge.relation_type.in_(COUNTED_ROLES),
        )
    )
    if start is not None:
        stmt = stmt.where(ExamAttempt.started_at >= start)
    for kid, selected, is_correct, at in db.execute(stmt):
        counts[kid].add(selected, is_correct, at, recent_from)

    attempted = select(AttemptAnswer.question_id).distinct().scalar_subquery()
    never: dict[uuid.UUID, int] = dict(
        db.execute(
            select(QuestionKnowledge.knowledge_id, func.count())
            .where(
                QuestionKnowledge.knowledge_id.in_(knowledge_ids),
                QuestionKnowledge.question_id.not_in(attempted),
            )
            .group_by(QuestionKnowledge.knowledge_id)
        ).all()  # type: ignore[arg-type]
    )

    review_rows = db.execute(
        select(
            ReviewItem.knowledge_id,
            ReviewItem.related_knowledge_id,
            ReviewItem.status,
            ReviewItem.due_at,
            ReviewItem.id,
        ).where(
            (ReviewItem.knowledge_id.in_(knowledge_ids))
            | (ReviewItem.related_knowledge_id.in_(knowledge_ids))
        )
    ).all()
    item_to_kids: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    next_due: dict[uuid.UUID, datetime] = {}
    for kid, rkid, status, due, item_id in review_rows:
        for k in (kid, rkid):
            if k in knowledge_ids:
                item_to_kids[item_id].add(k)
                if (
                    status == ReviewItemStatus.ACTIVE
                    and due is not None
                    and (k not in next_due or due < next_due[k])
                ):
                    next_due[k] = due
    events: dict[uuid.UUID, int] = defaultdict(int)
    last_rating: dict[uuid.UUID, tuple[datetime, str]] = {}
    if item_to_kids:
        for item_id, rating, at in db.execute(
            select(ReviewEvent.review_item_id, ReviewEvent.rating, ReviewEvent.reviewed_at).where(
                ReviewEvent.review_item_id.in_(list(item_to_kids))
            )
        ):
            for k in item_to_kids[item_id]:
                events[k] += 1
                if k not in last_rating or at > last_rating[k][0]:
                    last_rating[k] = (at, rating)

    out: dict[uuid.UUID, dict[str, Any]] = {}
    for kid in knowledge_ids:
        s = counts[kid].summary()
        s["never_attempted_questions"] = int(never.get(kid, 0))
        s["review_events"] = events.get(kid, 0)
        s["last_rating"] = last_rating[kid][1] if kid in last_rating else None
        s["next_due_at"] = next_due.get(kid)
        s["priority"] = priority(s, now)
        out[kid] = s
    return out


def category_stats(
    db: Session, window: str, now: datetime | None = None
) -> dict[str, dict[str, Any]]:
    now = now or utcnow()
    start = _window_start(window, now)
    stmt = (
        select(
            Question.question_type,
            AttemptAnswer.selected_answer,
            AttemptAnswer.is_correct,
            ExamAttempt.started_at,
        )
        .join(AttemptAnswer, AttemptAnswer.question_id == Question.id)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
    )
    if start is not None:
        stmt = stmt.where(ExamAttempt.started_at >= start)
    counts: dict[str, _Counts] = {
        c: _Counts() for c in ("vocabulary", "kanji", "grammar", "reading")
    }
    for qtype, selected, is_correct, at in db.execute(stmt):
        counts[category_for(qtype)].add(selected, is_correct, at, now - timedelta(days=7))
    return {c: v.summary() for c, v in counts.items()}


def weekly_timeline(
    db: Session, weeks: int = 8, now: datetime | None = None
) -> list[dict[str, Any]]:
    now = now or utcnow()
    start = (now - timedelta(weeks=weeks)).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets: dict[int, _Counts] = {i: _Counts() for i in range(weeks)}
    rows = db.execute(
        select(AttemptAnswer.selected_answer, AttemptAnswer.is_correct, ExamAttempt.started_at)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .where(ExamAttempt.started_at >= start)
    )
    for selected, is_correct, at in rows:
        idx = min(weeks - 1, int((at - start).total_seconds() // (7 * 86400)))
        buckets[idx].add(selected, is_correct, at, now)
    return [
        {"week_start": (start + timedelta(weeks=i)).date().isoformat(), **buckets[i].summary()}
        for i in range(weeks)
    ]


def review_progress(db: Session, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    start = now - timedelta(days=days)
    rows = db.execute(
        select(ReviewEvent.reviewed_at, ReviewEvent.rating, ReviewEvent.answer_correct).where(
            ReviewEvent.reviewed_at >= start
        )
    ).all()
    per_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {"reviews": 0, "answered": 0, "answered_correct": 0}
    )
    ratings: dict[str, int] = {"again": 0, "hard": 0, "good": 0, "easy": 0}
    for at, rating, correct in rows:
        day = at.date().isoformat()
        per_day[day]["reviews"] += 1
        ratings[rating] += 1
        if correct is not None:
            per_day[day]["answered"] += 1
            per_day[day]["answered_correct"] += int(correct)
    total_answered = sum(d["answered"] for d in per_day.values())
    total_correct = sum(d["answered_correct"] for d in per_day.values())
    due_now = db.scalar(
        select(func.count(ReviewItem.id)).where(
            ReviewItem.status == ReviewItemStatus.ACTIVE.value, ReviewItem.due_at <= now
        )
    )
    return {
        "days": days,
        "total_reviews": len(rows),
        "ratings": ratings,
        "answer_accuracy": round(total_correct / total_answered, 4) if total_answered else None,
        "answered": total_answered,
        "due_now": int(due_now or 0),
        "per_day": [{"date": d, **v} for d, v in sorted(per_day.items())],
    }


def improvement_after_review(
    db: Session, knowledge_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    """Exam error rate before vs after the first review of each item (counts shown, no verdict)."""
    first_review: dict[uuid.UUID, datetime] = {}
    for kid, at in db.execute(
        select(ReviewItem.knowledge_id, func.min(ReviewEvent.reviewed_at))
        .join(ReviewEvent, ReviewEvent.review_item_id == ReviewItem.id)
        .where(ReviewItem.knowledge_id.in_(knowledge_ids))
        .group_by(ReviewItem.knowledge_id)
    ):
        first_review[kid] = at
    out: dict[uuid.UUID, dict[str, Any]] = {}
    if not first_review:
        return out
    rows = db.execute(
        select(
            QuestionKnowledge.knowledge_id,
            AttemptAnswer.selected_answer,
            AttemptAnswer.is_correct,
            ExamAttempt.started_at,
        )
        .join(AttemptAnswer, AttemptAnswer.question_id == QuestionKnowledge.question_id)
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .where(
            QuestionKnowledge.knowledge_id.in_(list(first_review)),
            QuestionKnowledge.relation_type.in_(COUNTED_ROLES),
        )
    )
    before: dict[uuid.UUID, _Counts] = defaultdict(_Counts)
    after: dict[uuid.UUID, _Counts] = defaultdict(_Counts)
    for kid, selected, is_correct, at in rows:
        (after if at >= first_review[kid] else before)[kid].add(selected, is_correct, at, at)
    for kid, at in first_review.items():
        out[kid] = {
            "first_review_at": at,
            "before": before[kid].summary(),
            "after": after[kid].summary(),
        }
    return out
