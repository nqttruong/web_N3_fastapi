import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.responses import ERROR_RESPONSES, DataResponse
from app.core.security import get_principal
from app.database.session import get_db
from app.reviews import service
from app.reviews.models import ReviewItem
from app.reviews.schemas import (
    AnswerRequest,
    AnswerResult,
    Bucket,
    EventCreate,
    EventRead,
    EventResult,
    HistoryItem,
    ReviewItemRead,
    ReviewList,
    SessionCreate,
    SessionRead,
    StatusUpdate,
)

DB = Annotated[Session, Depends(get_db)]
router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
    dependencies=[Depends(get_principal)],
    responses=ERROR_RESPONSES,
)


def item_read(db: Session, item: ReviewItem, reason: str | None = None) -> ReviewItemRead:
    return ReviewItemRead.model_validate(
        {
            **{c: getattr(item, c) for c in ReviewItemRead.model_fields if hasattr(item, c)},
            "label": service.item_label(db, item),
            "blocked_reason": reason,
        }
    )


@router.get(
    "", summary="Review items by bucket: due | upcoming | completed | insufficient | suspended"
)
def list_reviews(db: DB, bucket: Annotated[Bucket, Query()] = "due") -> DataResponse[ReviewList]:
    items = service.list_items(db, bucket)
    return DataResponse(
        data=ReviewList(
            bucket=bucket, counts=service.counts(db), items=[item_read(db, i, r) for i, r in items]
        )
    )


@router.get("/due", summary="Items due now")
def due(db: DB) -> DataResponse[list[ReviewItemRead]]:
    return DataResponse(data=[item_read(db, i, r) for i, r in service.list_items(db, "due")])


@router.get("/history", summary="Review events (newest first)")
def history(
    db: DB,
    review_item_id: uuid.UUID | None = None,
    knowledge_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> DataResponse[list[HistoryItem]]:
    rows = service.history(
        db, review_item_id=review_item_id, knowledge_id=knowledge_id, limit=limit
    )
    return DataResponse(
        data=[
            HistoryItem(
                **EventRead.model_validate(e).model_dump(),
                label=service.item_label(db, i),
                review_type=i.review_type,
            )
            for e, i in rows
        ]
    )


@router.post(
    "/sessions", status_code=status.HTTP_201_CREATED, summary="Start a session from due items"
)
def create_session(payload: SessionCreate, db: DB) -> DataResponse[SessionRead]:
    session = service.create_session(db, payload.limit)
    return DataResponse(
        data=SessionRead(
            id=session.id,
            cards=[service.public_card(c) for c in session.cards],
            created_at=session.created_at,
            finished_at=session.finished_at,
        )
    )


@router.get("/sessions/{session_id}", summary="Resume a session (answers hidden until answered)")
def get_session(session_id: uuid.UUID, db: DB) -> DataResponse[SessionRead]:
    session = service.get_session(db, session_id)
    return DataResponse(
        data=SessionRead(
            id=session.id,
            cards=[service.public_card(c) for c in session.cards],
            created_at=session.created_at,
            finished_at=session.finished_at,
        )
    )


@router.post(
    "/sessions/{session_id}/answer",
    summary="Answer a card: grade + reveal (does NOT count as a review)",
)
def answer(session_id: uuid.UUID, payload: AnswerRequest, db: DB) -> DataResponse[AnswerResult]:
    return DataResponse(
        data=AnswerResult(
            **service.answer_card(db, session_id, payload.card_id, payload.selected_index)
        )
    )


@router.post("/events", summary="Record a rating (idempotent by request_id) and reschedule")
def create_event(payload: EventCreate, db: DB, response: Response) -> DataResponse[EventResult]:
    event, created = service.record_event(
        db,
        request_id=payload.request_id,
        review_item_id=payload.review_item_id,
        rating=payload.rating,
        timezone=payload.timezone,
        session_id=payload.session_id,
        card_id=payload.card_id,
        reviewed_at=payload.reviewed_at,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    item = db.get(ReviewItem, event.review_item_id)
    assert item is not None
    return DataResponse(
        data=EventResult(
            event=EventRead.model_validate(event), duplicate=not created, item=item_read(db, item)
        )
    )


@router.get("/{item_id}", summary="One review item")
def get_item(item_id: uuid.UUID, db: DB) -> DataResponse[ReviewItemRead]:
    item = db.get(ReviewItem, item_id)
    if item is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Không tìm thấy mục ôn tập.")
    return DataResponse(data=item_read(db, item, service.blocked_reason(db, item)))


@router.patch("/{item_id}", summary="Suspend / archive / reactivate")
def patch_item(item_id: uuid.UUID, payload: StatusUpdate, db: DB) -> DataResponse[ReviewItemRead]:
    item = service.set_status(db, item_id, payload.status, payload.version)
    return DataResponse(data=item_read(db, item, service.blocked_reason(db, item)))
