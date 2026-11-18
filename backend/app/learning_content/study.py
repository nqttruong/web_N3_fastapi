"""Single-user Web study API over licensed source content."""

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.responses import DataResponse
from app.core.security import get_principal
from app.database.enums import ReviewRating, SrsState
from app.database.session import get_db
from app.learning_content.course import group_course_items
from app.learning_content.mimikara_pdf import PACK_ID as PDF_PACK_ID
from app.learning_content.mimikara_pdf import extract_words
from app.learning_content.models import (
    LearningContentPack,
    LearningExample,
    LearningItem,
    LearningItemExample,
    LearningLesson,
)
from app.learning_content.pdf_import import pdf_inventory
from app.learning_content.service import enqueue_sync
from app.learning_content.source import source_inventory
from app.learning_content.study_models import (
    LearningExerciseAnswer,
    LearningSavedItem,
    LearningSourceRight,
    LearningStudyEvent,
    LearningStudyProgress,
    LearningStudySession,
)
from app.reviews.srs import DEFAULT_LADDER, NEW_ITEM, Ladder, SrsSnapshot, resolve_zone, schedule

router = APIRouter(
    prefix="/learning-content", tags=["learning-study"], dependencies=[Depends(get_principal)]
)
DB = Annotated[Session, Depends(get_db)]


class RightsInput(BaseModel):
    pack_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    rights_holder: str = Field(min_length=2, max_length=500)
    rights_basis: str = Field(min_length=10, max_length=2000)
    allowed_usage: str = Field(min_length=10, max_length=1000)
    attribution: str | None = Field(default=None, max_length=1000)
    scope: Literal["private"] = "private"
    approved: bool
    source_content_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class StartSession(BaseModel):
    mode: Literal["lesson", "course", "review", "saved"]
    pack_id: str | None = None
    lesson_id: str | None = None
    course_number: int | None = Field(default=None, ge=1, le=500)
    item_type: Literal["vocabulary", "kanji", "grammar"] | None = None
    time_zone: str = Field(default="Asia/Bangkok", max_length=100)


class RateCard(BaseModel):
    request_id: uuid.UUID
    rating: ReviewRating
    time_zone: str = Field(default="Asia/Bangkok", max_length=100)


class ExerciseAnswerInput(BaseModel):
    request_id: uuid.UUID
    selected_index: int = Field(ge=0)


def _visible() -> tuple[Any, ...]:
    return (
        LearningItem.is_archived.is_(False),
        LearningLesson.is_archived.is_(False),
        LearningContentPack.is_archived.is_(False),
    )


def _item_data(db: Session, item: LearningItem) -> dict[str, Any]:
    lesson = db.get(LearningLesson, item.lesson_id)
    examples = list(
        db.scalars(
            select(LearningExample)
            .join(LearningItemExample, LearningItemExample.example_id == LearningExample.id)
            .where(LearningItemExample.item_id == item.id, LearningExample.is_archived.is_(False))
            .order_by(LearningItemExample.order_index)
        )
    )
    progress = db.get(LearningStudyProgress, item.id)
    exercise_results: dict[str, dict[str, Any]] = {}
    if item.item_type == "grammar":
        for answer in db.scalars(
            select(LearningExerciseAnswer)
            .where(LearningExerciseAnswer.item_id == item.id)
            .order_by(
                LearningExerciseAnswer.answered_at.desc(), LearningExerciseAnswer.request_id.desc()
            )
        ):
            if answer.exercise_id not in exercise_results:
                exercise_results[answer.exercise_id] = {
                    "selected_index": answer.selected_index,
                    "is_correct": answer.is_correct,
                    "answered_at": answer.answered_at,
                }
    return {
        "id": str(item.id),
        "item_type": item.item_type,
        "pack_id": item.pack_id,
        "lesson_id": lesson.source_id if lesson else None,
        "lesson_title": lesson.title if lesson else None,
        "payload": item.payload,
        "examples": [e.payload for e in examples],
        "saved": db.get(LearningSavedItem, item.id) is not None,
        "progress": _progress_data(progress),
        "exercise_results": exercise_results,
    }


def _progress_data(row: LearningStudyProgress | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "state": row.state,
        "step_index": row.step_index,
        "interval_minutes": row.interval_minutes,
        "due_at": row.due_at,
        "last_reviewed_at": row.last_reviewed_at,
        "review_count": row.review_count,
        "lapse_count": row.lapse_count,
    }


@router.get("/rights/sources")
def rights_sources(
    db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> DataResponse[list[dict[str, Any]]]:
    if settings.android_learning_source_dir is None:
        raise HTTPException(503, "Nguồn Android chưa cấu hình")
    candidates = source_inventory(settings.android_learning_source_dir)
    pdf_source = pdf_inventory(settings)
    if pdf_source is not None:
        candidates.append(pdf_source)
    for entry in candidates:
        declaration = db.get(LearningSourceRight, (entry["pack_id"], entry["source_id"]))
        entry["declaration"] = (
            None
            if declaration is None
            else {
                "rights_holder": declaration.rights_holder,
                "rights_basis": declaration.rights_basis,
                "allowed_usage": declaration.allowed_usage,
                "attribution": declaration.attribution,
                "scope": declaration.scope,
                "approved": declaration.approved,
                "approved_at": declaration.approved_at.isoformat()
                if declaration.approved_at
                else None,
                "source_content_hash": declaration.source_content_hash,
            }
        )
    return DataResponse(data=candidates)


@router.get("/rights/pdf-preview")
def pdf_preview(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataResponse[dict[str, Any]]:
    """Read-only sample for human rights and parser review before import."""
    if not settings.mimikara_pdf_path.is_file():
        raise HTTPException(404, "Không tìm thấy PDF Mimikara đã cấu hình")
    digest, rows = extract_words(settings.mimikara_pdf_path)
    samples = [rows[index] for index in (0, 1, 2, 438, 439, 440, 877, 878, 879)]
    return DataResponse(
        data={
            "source_content_hash": digest,
            "row_count": len(rows),
            "samples": [
                {
                    "number": row.number,
                    "expression": row.expression,
                    "reading": row.reading,
                    "meaning_vi": row.meaning_vi,
                    "source_page": row.page,
                    "source_lesson_number": row.lesson_number,
                }
                for row in samples
            ],
        }
    )


@router.put("/rights/sources")
def set_source_rights(
    payload: RightsInput, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> DataResponse[dict[str, Any]]:
    if settings.android_learning_source_dir is None:
        raise HTTPException(503, "Nguồn Android chưa cấu hình")
    candidates = source_inventory(settings.android_learning_source_dir)
    pdf_source = pdf_inventory(settings)
    if pdf_source is not None:
        candidates.append(pdf_source)
    match = next(
        (
            s
            for s in candidates
            if s["pack_id"] == payload.pack_id and s["source_id"] == payload.source_id
        ),
        None,
    )
    if match is None:
        raise HTTPException(404, "Không tìm thấy source hiện có")
    if (
        payload.pack_id == PDF_PACK_ID
        and payload.approved
        and payload.source_content_hash != match["source_content_hash"]
    ):
        raise HTTPException(409, "SHA-256 của PDF đã thay đổi; xem lại nguồn trước khi duyệt")
    row = db.get(LearningSourceRight, (payload.pack_id, payload.source_id))
    if row is None:
        row = LearningSourceRight(pack_id=payload.pack_id, source_id=payload.source_id)
        db.add(row)
    row.source_name = str(match["source_name"])
    row.source_content_hash = (
        str(match["source_content_hash"])
        if payload.pack_id == PDF_PACK_ID and payload.approved
        else None
    )
    row.rights_holder = payload.rights_holder.strip()
    row.rights_basis = payload.rights_basis.strip()
    row.allowed_usage = payload.allowed_usage.strip()
    row.attribution = payload.attribution
    row.scope = "private"
    row.approved = payload.approved
    row.approved_at = datetime.now(UTC) if payload.approved else None
    db.commit()
    run = enqueue_sync(
        db, "manual", source_kind="pdf" if payload.pack_id == PDF_PACK_ID else "android"
    )
    return DataResponse(
        data={
            "pack_id": row.pack_id,
            "source_id": row.source_id,
            "approved": row.approved,
            "sync_run_id": str(run.id),
        }
    )


@router.get("/lessons")
def lessons(
    db: DB, item_type: Annotated[str | None, Query(alias="type")] = None
) -> DataResponse[list[dict[str, Any]]]:
    stmt = (
        select(
            LearningLesson,
            LearningContentPack,
            func.count(LearningItem.id),
            func.count(LearningStudyProgress.item_id),
        )
        .join(LearningContentPack, LearningContentPack.id == LearningLesson.pack_id)
        .join(LearningItem, LearningItem.lesson_id == LearningLesson.id)
        .outerjoin(LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id)
        .where(*_visible())
        .group_by(LearningLesson.id, LearningContentPack.id)
        .order_by(
            LearningContentPack.jlpt_level, LearningContentPack.title, LearningLesson.order_index
        )
    )
    if item_type:
        if item_type not in {"vocabulary", "kanji", "grammar"}:
            raise HTTPException(422, "Loại nội dung không hợp lệ")
        stmt = stmt.where(LearningItem.item_type == item_type)
    return DataResponse(
        data=[
            {
                "pack_id": pack.id,
                "pack_title": pack.title,
                "lesson_id": lesson.source_id,
                "number": lesson.number,
                "title": lesson.title,
                "description": lesson.description,
                "total": total,
                "learned": learned,
                "jlpt_level": pack.jlpt_level,
            }
            for lesson, pack, total, learned in db.execute(stmt)
        ]
    )


@router.get("/lessons/{pack_id}/{lesson_id}")
def lesson_detail(pack_id: str, lesson_id: str, db: DB) -> DataResponse[dict[str, Any]]:
    lesson = db.scalar(
        select(LearningLesson)
        .join(LearningContentPack, LearningContentPack.id == LearningLesson.pack_id)
        .where(
            LearningLesson.pack_id == pack_id,
            LearningLesson.source_id == lesson_id,
            LearningLesson.is_archived.is_(False),
            LearningContentPack.is_archived.is_(False),
        )
    )

    if lesson is None:
        raise HTTPException(404, "Không tìm thấy bài học")
    items = list(
        db.scalars(
            select(LearningItem)
            .where(LearningItem.lesson_id == lesson.id, LearningItem.is_archived.is_(False))
            .order_by(LearningItem.order_index)
        )
    )
    return DataResponse(
        data={
            "pack_id": pack_id,
            "lesson_id": lesson_id,
            "number": lesson.number,
            "title": lesson.title,
            "description": lesson.description,
            "items": [_item_data(db, item) for item in items],
        }
    )


def _course_groups(db: Session) -> list[dict[str, list[LearningItem]]]:
    rows = db.scalars(
        select(LearningItem)
        .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(*_visible(), LearningItem.jlpt_level == "N3")
        .order_by(
            LearningItem.item_type,
            LearningContentPack.id,
            LearningLesson.order_index,
            LearningItem.order_index,
            LearningItem.source_ref,
        )
    )
    by_type: dict[str, list[LearningItem]] = {
        kind: [] for kind in ("vocabulary", "grammar", "kanji")
    }
    for item in rows:
        by_type[item.item_type].append(item)
    return group_course_items(by_type)


@router.get("/course")
def course_lessons(db: DB) -> DataResponse[list[dict[str, Any]]]:
    result = []
    now = datetime.now(UTC)
    for number, group in enumerate(_course_groups(db), 1):
        ids = [item.id for rows in group.values() for item in rows]
        progress = list(
            db.scalars(select(LearningStudyProgress).where(LearningStudyProgress.item_id.in_(ids)))
        )
        studied_ids = set(
            db.scalars(
                select(LearningStudyEvent.item_id).where(LearningStudyEvent.item_id.in_(ids))
            )
        )
        learned = len(studied_ids | {row.item_id for row in progress})
        due = sum(row.due_at <= now for row in progress)
        last_event = db.scalar(
            select(func.max(LearningStudyEvent.reviewed_at)).where(
                LearningStudyEvent.item_id.in_(ids)
            )
        )
        result.append(
            {
                "number": number,
                "title": f"Bài {number:02d}",
                "counts": {kind: len(rows) for kind, rows in group.items()},
                "total": len(ids),
                "learned": learned,
                "due": due,
                "status": "needs_review"
                if due
                else "completed"
                if learned == len(ids)
                else "in_progress"
                if learned
                else "new",
                "last_studied_at": max(
                    (
                        value
                        for value in [last_event, *(row.last_reviewed_at for row in progress)]
                        if value is not None
                    ),
                    default=None,
                ),
            }
        )
    return DataResponse(data=result)


@router.get("/course/{number}")
def course_lesson(number: int, db: DB) -> DataResponse[dict[str, Any]]:
    groups = _course_groups(db)
    if number < 1 or number > len(groups):
        raise HTTPException(404, "Không tìm thấy bài tổng hợp")
    group = groups[number - 1]
    return DataResponse(
        data={
            "number": number,
            "title": f"Bài {number:02d}",
            "sections": {
                kind: [_item_data(db, item) for item in rows] for kind, rows in group.items()
            },
        }
    )


@router.get("/study/overview")
def study_overview(
    db: DB, time_zone: Annotated[str, Query(max_length=100)] = "Asia/Bangkok"
) -> DataResponse[dict[str, Any]]:
    now = datetime.now(UTC)
    counts: dict[str, int] = dict(
        db.execute(
            select(LearningItem.item_type, func.count())
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .where(*_visible())
            .group_by(LearningItem.item_type)
        )
        .tuples()
        .all()
    )
    progress_base = (
        select(LearningItem.item_type, func.count())
        .join(LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id)
        .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(*_visible())
    )
    learned_by_type = dict(
        db.execute(progress_base.group_by(LearningItem.item_type)).tuples().all()
    )
    learned = sum(learned_by_type.values())
    due = (
        db.scalar(
            select(func.count())
            .select_from(LearningItem)
            .join(LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id)
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .where(*_visible(), LearningStudyProgress.due_at <= now)
        )
        or 0
    )
    new_by_type = dict(
        db.execute(
            select(LearningItem.item_type, func.count())
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .outerjoin(LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id)
            .where(*_visible(), LearningStudyProgress.item_id.is_(None))
            .group_by(LearningItem.item_type)
        )
        .tuples()
        .all()
    )
    zone = resolve_zone(time_zone)
    local = now.astimezone(zone)
    today_start = datetime.combine(local.date(), time.min, tzinfo=zone).astimezone(UTC)
    tomorrow_start = datetime.combine(
        local.date() + timedelta(days=1), time.min, tzinfo=zone
    ).astimezone(UTC)
    consumed_new = dict(
        db.execute(
            select(LearningItem.item_type, func.count())
            .join(LearningStudyEvent, LearningStudyEvent.item_id == LearningItem.id)
            .where(
                LearningStudyEvent.was_new.is_(True),
                LearningStudyEvent.origin == "web",
                LearningStudyEvent.reviewed_at >= today_start,
                LearningStudyEvent.reviewed_at < tomorrow_start,
            )
            .group_by(LearningItem.item_type)
        )
        .tuples()
        .all()
    )
    available_new = sum(
        min(max(0, cap - consumed_new.get(kind, 0)), new_by_type.get(kind, 0))
        for kind, cap in (("vocabulary", 20), ("kanji", 10), ("grammar", 10))
    )
    saved = (
        db.scalar(
            select(func.count())
            .select_from(LearningSavedItem)
            .join(LearningItem, LearningItem.id == LearningSavedItem.item_id)
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .where(*_visible())
        )
        or 0
    )
    last = db.scalar(select(func.max(LearningStudyEvent.reviewed_at)))
    active = db.scalar(
        select(LearningStudySession)
        .where(LearningStudySession.finished_at.is_(None))
        .order_by(LearningStudySession.started_at.desc())
    )
    recent = list(
        db.execute(
            select(
                LearningStudyEvent.item_id,
                LearningStudyEvent.rating,
                LearningStudyEvent.reviewed_at,
                LearningStudyEvent.origin,
                LearningItem.item_type,
                LearningItem.payload,
            )
            .join(LearningItem, LearningItem.id == LearningStudyEvent.item_id)
            .order_by(LearningStudyEvent.reviewed_at.desc())
            .limit(8)
        )
    )
    return DataResponse(
        data={
            "content_counts": counts,
            "learned": learned,
            "learned_by_type": learned_by_type,
            "due": due,
            "available_new": available_new,
            "saved": saved,
            "last_activity_at": last,
            "active_session_id": str(active.id) if active else None,
            "recent_activity": [
                {
                    "item_id": str(item_id),
                    "item_type": item_type,
                    "title": str(
                        content.get(
                            "expression"
                            if item_type == "vocabulary"
                            else "character"
                            if item_type == "kanji"
                            else "pattern",
                            "",
                        )
                    ),
                    "rating": rating,
                    "reviewed_at": reviewed_at,
                    "origin": origin,
                }
                for item_id, rating, reviewed_at, origin, item_type, content in recent
            ],
        }
    )


@router.put("/items/{item_id}/saved")
def save_item(item_id: uuid.UUID, db: DB) -> DataResponse[dict[str, bool]]:
    if (
        db.scalar(
            select(LearningItem.id)
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .where(LearningItem.id == item_id, *_visible())
        )
        is None
    ):
        raise HTTPException(404, "Không tìm thấy nội dung")
    if db.get(LearningSavedItem, item_id) is None:
        db.add(LearningSavedItem(item_id=item_id))
        db.commit()
    return DataResponse(data={"saved": True})


@router.delete("/items/{item_id}/saved")
def unsave_item(item_id: uuid.UUID, db: DB) -> DataResponse[dict[str, bool]]:
    row = db.get(LearningSavedItem, item_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return DataResponse(data={"saved": False})


@router.get("/saved")
def saved_items(db: DB) -> DataResponse[list[dict[str, Any]]]:
    items = list(
        db.scalars(
            select(LearningItem)
            .join(LearningSavedItem, LearningSavedItem.item_id == LearningItem.id)
            .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
            .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
            .where(*_visible())
            .order_by(LearningSavedItem.saved_at.desc())
        )
    )
    return DataResponse(data=[_item_data(db, item) for item in items])


@router.post("/items/{item_id}/exercises/{exercise_id}/answers", status_code=201)
def answer_exercise(
    item_id: uuid.UUID, exercise_id: str, payload: ExerciseAnswerInput, db: DB
) -> DataResponse[dict[str, Any]]:
    item = db.scalar(
        select(LearningItem)
        .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(LearningItem.id == item_id, LearningItem.item_type == "grammar", *_visible())
        .with_for_update(of=LearningItem)
    )
    if item is None:
        raise HTTPException(404, "Không tìm thấy mục ngữ pháp")
    previous = db.get(LearningExerciseAnswer, payload.request_id)
    if previous is not None:
        if (
            previous.item_id != item_id
            or previous.exercise_id != exercise_id
            or previous.selected_index != payload.selected_index
        ):
            raise HTTPException(409, "request_id đã được dùng cho đáp án khác")
        saved = previous.exercise_snapshot
        return DataResponse(
            data={
                "selected_index": previous.selected_index,
                "is_correct": previous.is_correct,
                "answer_index": saved["answerIndex"],
                "explanation_vi": saved.get("explanationVi"),
                "duplicate": True,
            }
        )
    exercises = item.payload.get("exercises", [])
    exercise = next(
        (
            entry
            for entry in exercises
            if isinstance(entry, dict) and entry.get("id") == exercise_id
        ),
        None,
    )
    if exercise is None:
        raise HTTPException(404, "Không tìm thấy bài luyện trong nội dung nguồn")
    options = exercise.get("options", [])
    if not isinstance(options, list) or payload.selected_index >= len(options):
        raise HTTPException(422, "Lựa chọn ngoài phạm vi")
    correct = payload.selected_index == exercise["answerIndex"]
    db.add(
        LearningExerciseAnswer(
            request_id=payload.request_id,
            item_id=item_id,
            exercise_id=exercise_id,
            selected_index=payload.selected_index,
            is_correct=correct,
            source_content_hash=item.content_hash,
            exercise_snapshot=dict(exercise),
        )
    )
    db.commit()
    return DataResponse(
        data={
            "selected_index": payload.selected_index,
            "is_correct": correct,
            "answer_index": exercise["answerIndex"],
            "explanation_vi": exercise.get("explanationVi"),
            "duplicate": False,
        }
    )


def _session_data(db: Session, row: LearningStudySession) -> dict[str, Any]:
    current = None
    if row.current_index < len(row.item_ids):
        item = db.get(LearningItem, uuid.UUID(row.item_ids[row.current_index]))
        if item is not None:
            current = _item_data(db, item)
    ratings: dict[str, int] = dict(
        db.execute(
            select(LearningStudyEvent.rating, func.count())
            .where(LearningStudyEvent.session_id == row.id)
            .group_by(LearningStudyEvent.rating)
        )
        .tuples()
        .all()
    )
    return {
        "id": str(row.id),
        "mode": row.mode,
        "position": row.current_index,
        "total": len(row.item_ids),
        "current": current,
        "finished_at": row.finished_at,
        "ratings": ratings,
    }


@router.post("/study/sessions", status_code=201)
def start_session(payload: StartSession, db: DB) -> DataResponse[dict[str, Any]]:
    stmt = (
        select(LearningItem.id)
        .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(*_visible())
    )
    if payload.mode == "course":
        groups = _course_groups(db)
        if payload.course_number is None or payload.course_number > len(groups):
            raise HTTPException(404, "Không tìm thấy bài tổng hợp")
        group = groups[payload.course_number - 1]
        ids = [str(item.id) for kind in ("vocabulary", "grammar", "kanji") for item in group[kind]]
        if payload.item_type:
            ids = [str(item.id) for item in group[payload.item_type]]
        if not ids:
            raise HTTPException(404, "Bài này không có mục thuộc nhóm đã chọn")
        row = LearningStudySession(mode=payload.mode, item_ids=ids)
        db.add(row)
        db.commit()
        db.refresh(row)
        return DataResponse(data=_session_data(db, row))
    if payload.mode == "lesson":
        if not payload.pack_id or not payload.lesson_id:
            raise HTTPException(422, "Chọn bài học")
        stmt = stmt.where(
            LearningItem.pack_id == payload.pack_id, LearningLesson.source_id == payload.lesson_id
        )
    elif payload.mode == "review":
        pass
    else:
        stmt = stmt.join(LearningSavedItem, LearningSavedItem.item_id == LearningItem.id)
    if payload.item_type:
        stmt = stmt.where(LearningItem.item_type == payload.item_type)
    if payload.mode == "review":
        zone = resolve_zone(payload.time_zone)
        local = datetime.now(UTC).astimezone(zone)
        today_start = datetime.combine(local.date(), time.min, tzinfo=zone).astimezone(UTC)
        tomorrow_start = datetime.combine(
            local.date() + timedelta(days=1), time.min, tzinfo=zone
        ).astimezone(UTC)
        today_events = (
            db.execute(
                select(LearningStudyEvent.item_id, LearningStudyEvent.was_new).where(
                    LearningStudyEvent.origin == "web",
                    LearningStudyEvent.reviewed_at >= today_start,
                    LearningStudyEvent.reviewed_at < tomorrow_start,
                )
            )
            .tuples()
            .all()
        )
        today_new: dict[str, int] = {}
        for event_item, was_new in today_events:
            if was_new:
                item = db.get(LearningItem, event_item)
                if item is not None:
                    today_new[item.item_type] = today_new.get(item.item_type, 0) + 1
        reviews_left = max(0, 200 - sum(not was_new for _, was_new in today_events))
        due_ids = list(
            db.scalars(
                stmt.join(LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id)
                .where(LearningStudyProgress.due_at <= datetime.now(UTC))
                .order_by(LearningStudyProgress.due_at)
                .limit(reviews_left)
            )
        )
        new_ids = list(
            db.scalars(
                stmt.outerjoin(
                    LearningStudyProgress, LearningStudyProgress.item_id == LearningItem.id
                )
                .where(LearningStudyProgress.item_id.is_(None))
                .order_by(LearningLesson.order_index, LearningItem.order_index)
            )
        )
        left = {
            "vocabulary": max(0, 20 - today_new.get("vocabulary", 0)),
            "kanji": max(0, 10 - today_new.get("kanji", 0)),
            "grammar": max(0, 10 - today_new.get("grammar", 0)),
        }
        chosen = list(due_ids)
        for item_id in new_ids:
            item = db.get(LearningItem, item_id)
            if item is not None and left[item.item_type] > 0:
                chosen.append(item_id)
                left[item.item_type] -= 1
        ids = [str(value) for value in chosen]
    else:
        ids = [
            str(value)
            for value in db.scalars(
                stmt.order_by(LearningLesson.order_index, LearningItem.order_index).limit(500)
            )
        ]
    if not ids:
        raise HTTPException(404, "Chưa có thẻ phù hợp")
    row = LearningStudySession(mode=payload.mode, item_ids=ids)
    db.add(row)
    db.commit()
    db.refresh(row)
    return DataResponse(data=_session_data(db, row))


@router.get("/study/sessions/{session_id}")
def get_session(session_id: uuid.UUID, db: DB) -> DataResponse[dict[str, Any]]:
    row = db.get(LearningStudySession, session_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy phiên học")
    return DataResponse(data=_session_data(db, row))


@router.post("/study/sessions/{session_id}/rate")
def rate_card(session_id: uuid.UUID, payload: RateCard, db: DB) -> DataResponse[dict[str, Any]]:
    row = db.scalar(
        select(LearningStudySession).where(LearningStudySession.id == session_id).with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy phiên học")
    previous = db.get(LearningStudyEvent, payload.request_id)
    if previous is not None:
        if previous.session_id != session_id or previous.rating != payload.rating.value:
            raise HTTPException(409, "request_id đã được dùng cho đánh giá khác")
        return DataResponse(data=_session_data(db, row))
    if row.finished_at is not None or row.current_index >= len(row.item_ids):
        raise HTTPException(409, "Phiên học đã hoàn thành")
    item_id = uuid.UUID(row.item_ids[row.current_index])
    db.scalar(select(LearningItem.id).where(LearningItem.id == item_id).with_for_update())
    progress = db.get(LearningStudyProgress, item_id)
    current = (
        NEW_ITEM
        if progress is None
        else SrsSnapshot(
            SrsState(progress.state),
            progress.step_index,
            progress.interval_minutes,
            progress.due_at,
            progress.last_reviewed_at,
            progress.review_count,
            progress.lapse_count,
        )
    )
    now = datetime.now(UTC)
    scheduled = row.mode == "review"
    next_state = (
        schedule(
            current,
            payload.rating,
            now,
            resolve_zone(payload.time_zone),
            Ladder.parse(DEFAULT_LADDER),
        )
        if scheduled
        else current
    )
    if scheduled:
        assert next_state.due_at is not None
        if progress is None:
            progress = LearningStudyProgress(item_id=item_id)
            db.add(progress)
        progress.state = next_state.state.value
        progress.step_index = next_state.step_index or 0
        progress.interval_minutes = next_state.interval_minutes
        progress.due_at = next_state.due_at
        progress.last_reviewed_at = now
        progress.review_count = next_state.review_count
        progress.lapse_count = next_state.lapse_count
    db.add(
        LearningStudyEvent(
            request_id=payload.request_id,
            item_id=item_id,
            session_id=session_id,
            rating=payload.rating.value,
            reviewed_at=now,
            interval_before_minutes=current.interval_minutes,
            interval_after_minutes=next_state.interval_minutes,
            due_at_after=next_state.due_at or now,
            was_new=scheduled and current.state == SrsState.NEW,
            origin="web" if scheduled else "web_practice",
        )
    )
    row.current_index += 1
    if row.current_index == len(row.item_ids):
        row.finished_at = now
    db.commit()
    return DataResponse(data=_session_data(db, row))
