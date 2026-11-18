from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.schemas import DashboardSummary
from app.attempts.models import AttemptAnswer, ExamAttempt
from app.attempts.schemas import AttemptSummary, accuracy
from app.attempts.service import list_attempts
from app.core.responses import PageParams
from app.exams.models import Exam, Question
from app.exams.schemas import ExamListFilters, ExamRead
from app.exams.service import list_exams

RECENT_LIMIT = 5


def dashboard_summary(db: Session) -> DashboardSummary:
    totals = db.execute(
        select(
            func.count(ExamAttempt.id),
            func.coalesce(func.sum(ExamAttempt.correct_count), 0),
            func.coalesce(func.sum(ExamAttempt.incorrect_count), 0),
            func.coalesce(func.sum(ExamAttempt.unanswered_count), 0),
            func.coalesce(func.sum(ExamAttempt.ungraded_count), 0),
        )
    ).one()
    attempts, correct, incorrect, unanswered, ungraded = (int(v) for v in totals)
    recent_page = PageParams(page=1, page_size=RECENT_LIMIT)
    recent_exams: list[ExamRead] = list_exams(db, ExamListFilters(), recent_page)[0]
    recent_attempts: list[AttemptSummary] = list_attempts(db, recent_page)[0]
    return DashboardSummary(
        total_exams=db.scalar(select(func.count(Exam.id))) or 0,
        total_questions=db.scalar(select(func.count(Question.id))) or 0,
        total_attempts=attempts,
        total_correct=correct,
        total_incorrect=incorrect,
        total_unanswered=unanswered,
        total_ungraded=ungraded,
        accuracy=accuracy(correct, incorrect),
        recent_exams=recent_exams,
        recent_attempts=recent_attempts,
    )


def jlpt_report(db: Session) -> dict[str, object]:
    """Exact aggregates over persisted Web attempts; no pass estimate or inferred Android data."""
    from app.database.enums import QuestionType

    rows = db.execute(
        select(
            ExamAttempt.id,
            ExamAttempt.exam_id,
            ExamAttempt.started_at,
            ExamAttempt.completed_at,
            ExamAttempt.source,
            ExamAttempt.correct_count,
            ExamAttempt.incorrect_count,
            ExamAttempt.unanswered_count,
            ExamAttempt.ungraded_count,
            Exam.title,
        )
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .order_by(ExamAttempt.started_at, ExamAttempt.id)
    ).all()
    answer_rows = db.execute(
        select(
            AttemptAnswer.selected_answer,
            AttemptAnswer.is_correct,
            Question.question_type,
            Exam.category,
        )
        .join(ExamAttempt, ExamAttempt.id == AttemptAnswer.attempt_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .join(Question, Question.id == AttemptAnswer.question_id)
    ).all()
    skill_types = {
        "kanji": {QuestionType.KANJI_READING.value, QuestionType.ORTHOGRAPHY.value},
        "grammar": {
            QuestionType.GRAMMAR_FORM.value,
            QuestionType.SENTENCE_COMPOSITION.value,
            QuestionType.TEXT_GRAMMAR.value,
        },
        "reading": {
            QuestionType.READING_SHORT.value,
            QuestionType.READING_MEDIUM.value,
            QuestionType.READING_LONG.value,
            QuestionType.INFORMATION_RETRIEVAL.value,
        },
    }
    skills: dict[str, dict[str, int]] = {
        name: {"correct": 0, "incorrect": 0, "unanswered": 0, "ungraded": 0, "total": 0}
        for name in ("vocabulary", "kanji", "grammar", "reading")
    }
    mistakes_by_type: dict[str, int] = defaultdict(int)
    for selected, is_correct, question_type, exam_category in answer_rows:
        category = next(
            (name for name, values in skill_types.items() if question_type in values), None
        )
        if category is None:
            # Android maps OTHER to its section. Web has no section field; the exam category is
            # the only recorded source that can be used without guessing.
            category = exam_category if question_type == QuestionType.OTHER.value else "vocabulary"
        bucket = skills[category]
        bucket["total"] += 1
        if selected is None:
            bucket["unanswered"] += 1
        elif is_correct is None:
            bucket["ungraded"] += 1
        elif is_correct:
            bucket["correct"] += 1
        else:
            bucket["incorrect"] += 1
            mistakes_by_type[question_type] += 1

    by_exam: dict[object, dict[str, Any]] = {}
    by_week: dict[str, dict[str, int]] = {}
    for row in rows:
        exam_id = row.exam_id
        exam_bucket = by_exam.setdefault(
            exam_id,
            {
                "exam_id": str(exam_id),
                "exam_title": row.title,
                "attempts": 0,
                "latest_at": row.started_at,
            },
        )
        exam_bucket["attempts"] = int(exam_bucket["attempts"]) + 1
        exam_bucket["latest_at"] = row.started_at
        # ISO week makes the trend stable across year boundaries.
        iso = row.started_at.date().isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
        point = by_week.setdefault(
            week, {"attempts": 0, "correct": 0, "incorrect": 0, "unanswered": 0, "ungraded": 0}
        )
        point["attempts"] += 1
        point["correct"] += row.correct_count
        point["incorrect"] += row.incorrect_count
        point["unanswered"] += row.unanswered_count
        point["ungraded"] += row.ungraded_count

    total_correct = sum(int(r.correct_count) for r in rows)
    total_incorrect = sum(int(r.incorrect_count) for r in rows)
    total_unanswered = sum(int(r.unanswered_count) for r in rows)
    total_ungraded = sum(int(r.ungraded_count) for r in rows)
    graded = total_correct + total_incorrect
    total_questions = total_correct + total_incorrect + total_unanswered + total_ungraded
    durations = [
        int((row.completed_at - row.started_at).total_seconds())
        for row in rows
        if row.completed_at is not None
    ]
    source_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        source_counts[row.source] += 1
    return {
        "attempt_count": len(rows),
        "correct": total_correct,
        "incorrect": total_incorrect,
        "unanswered": total_unanswered,
        "ungraded": total_ungraded,
        "accuracy": round(total_correct / graded, 4) if graded else None,
        "correct_over_all": round(total_correct / total_questions, 4) if total_questions else None,
        "average_duration_seconds": round(sum(durations) / len(durations)) if durations else None,
        "skill_results": skills,
        "mistakes_by_question_type": dict(
            sorted(mistakes_by_type.items(), key=lambda x: (-x[1], x[0]))
        ),
        "trend": [{"week": key, **by_week[key]} for key in sorted(by_week)],
        "repeated_exams": sorted(
            by_exam.values(), key=lambda x: (-int(x["attempts"]), str(x["exam_id"]))
        )[:10],
        "sources": dict(source_counts),
        "android_attempt_count": None,
        "listening_data_available": False,
        "score_note": "Đây là số câu đúng và tỷ lệ chính xác, không phải điểm JLPT chính thức.",
    }


def weakness_report(db: Session, window: str, limit: int) -> dict[str, object]:
    from app.analytics import weakness
    from app.database.enums import KnowledgeStatus
    from app.knowledge.models import KnowledgeItem

    items = list(
        db.scalars(
            select(KnowledgeItem).where(KnowledgeItem.status == KnowledgeStatus.ACTIVE.value)
        )
    )
    stats = weakness.knowledge_stats(db, [k.id for k in items], window=window)
    ranked = sorted(
        items,
        key=lambda k: (
            {"review_now": 0, "due_soon": 1, "stable": 2, "insufficient_data": 3}[
                stats[k.id]["priority"]
            ],
            -(stats[k.id]["error_rate_low"] or 0),
            -stats[k.id]["incorrect"],
        ),
    )
    priorities: dict[str, int] = {
        "review_now": 0,
        "due_soon": 0,
        "stable": 0,
        "insufficient_data": 0,
    }
    by_type: dict[str, dict[str, int]] = {}
    for k in items:
        priorities[stats[k.id]["priority"]] += 1
        t = by_type.setdefault(k.knowledge_type, {"items": 0, "incorrect": 0})
        t["items"] += 1
        t["incorrect"] += stats[k.id]["incorrect"]
    improvement = weakness.improvement_after_review(db, [k.id for k in items])
    return {
        "window": window,
        "categories": weakness.category_stats(db, window),
        "priorities": priorities,
        "knowledge_types": by_type,
        "top_knowledge": [
            {
                "knowledge_id": str(k.id),
                "title": k.title,
                "knowledge_type": k.knowledge_type,
                **stats[k.id],
            }
            for k in ranked[:limit]
        ],
        "timeline": weakness.weekly_timeline(db),
        "improvement": [
            {"knowledge_id": str(kid), "title": next(k.title for k in items if k.id == kid), **v}
            for kid, v in improvement.items()
        ],
        "min_observations": weakness.MIN_OBSERVATIONS,
    }


def knowledge_report(db: Session, knowledge_id: object) -> dict[str, object]:
    import uuid

    from app.analytics import weakness
    from app.core.errors import NotFoundError
    from app.knowledge.models import KnowledgeItem

    assert isinstance(knowledge_id, uuid.UUID)
    k = db.get(KnowledgeItem, knowledge_id)
    if k is None:
        raise NotFoundError("Không tìm thấy mục kiến thức.")
    return {
        "knowledge_id": str(k.id),
        "title": k.title,
        "windows": {
            w: weakness.knowledge_stats(db, [k.id], window=w)[k.id] for w in ("7d", "30d", "all")
        },
        "improvement": weakness.improvement_after_review(db, [k.id]).get(k.id),
    }
