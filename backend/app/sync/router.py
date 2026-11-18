import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.responses import DataResponse
from app.database.session import get_db
from app.exams.models import Question
from app.explanations.context import current_content_hash
from app.sync.admin import require_https_for_remote_sync, require_sync_admin
from app.sync.device import (
    SyncDevice,
    get_device,
    issue_pairing_code,
    pair_device,
)
from app.sync.models import AndroidReviewEvent, SyncChange
from app.sync.qr import router as qr_router
from app.sync.schemas import (
    ChangePage,
    ChangeRead,
    DeviceRead,
    PairingCodeCreate,
    PairingCodeRead,
    PairRequest,
    PushAck,
    PushRequest,
    SyncDeviceAdminRead,
)

DB = Annotated[Session, Depends(get_db)]
router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(require_https_for_remote_sync)],
)
router.include_router(qr_router)


@router.post("/pair", status_code=status.HTTP_201_CREATED)
def pair(
    payload: PairRequest,
    db: DB,
    request: Request,
    pairing_key: Annotated[str | None, Header(alias="X-Pairing-Key")] = None,
) -> DataResponse[DeviceRead]:
    source_address = request.client.host if request.client else "unknown"
    device, token = pair_device(
        db, pairing_code=pairing_key or "", name=payload.device_name, source_address=source_address
    )
    return DataResponse(
        data=DeviceRead(device_id=device.id, device_name=device.name, access_token=token)
    )


@router.post(
    "/admin/pairing-codes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_sync_admin)],
    summary="Create a one-time, expiring Android pairing code",
)
def create_pairing_code(payload: PairingCodeCreate, db: DB) -> DataResponse[PairingCodeRead]:
    code, row = issue_pairing_code(db, expires_in_minutes=payload.expires_in_minutes)
    return DataResponse(
        data=PairingCodeRead(
            pairing_code=code,
            expires_at=row.expires_at,
            expires_in_minutes=payload.expires_in_minutes,
        )
    )


@router.get(
    "/admin/devices",
    dependencies=[Depends(require_sync_admin)],
    summary="List paired Android devices and their observed sync activity",
)
def list_devices(db: DB) -> DataResponse[list[SyncDeviceAdminRead]]:
    devices = list(db.scalars(select(SyncDevice).order_by(SyncDevice.created_at.desc())))
    return DataResponse(
        data=[
            SyncDeviceAdminRead(
                device_id=device.id,
                device_name=device.name,
                paired_at=device.created_at,
                last_seen_at=device.last_seen_at,
                last_pull_at=device.last_pull_at,
                last_push_at=device.last_push_at,
                revoked_at=device.revoked_at,
            )
            for device in devices
        ]
    )


@router.delete(
    "/admin/devices/{device_id}",
    dependencies=[Depends(require_sync_admin)],
    summary="Revoke one Android device credential",
)
def revoke_device(device_id: uuid.UUID, db: DB) -> DataResponse[dict[str, str]]:
    device = db.get(SyncDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")
    if device.revoked_at is None:
        device.revoked_at = datetime.now(UTC)
        db.commit()
    return DataResponse(data={"status": "revoked", "device_id": str(device_id)})


@router.post("/disconnect", status_code=status.HTTP_200_OK)
def disconnect_device(
    db: DB, device: Annotated[SyncDevice, Depends(get_device)]
) -> DataResponse[dict[str, str]]:
    device.revoked_at = datetime.now(UTC)
    db.commit()
    return DataResponse(data={"status": "revoked"})


def _payload(db: Session, change: SyncChange) -> dict[str, Any] | None:
    if change.operation == "delete":
        return None
    row = change.payload or {}

    def zero_based(value: Any) -> int | None:
        return value - 1 if isinstance(value, int) and value > 0 else None

    if change.entity_type == "exam":
        return {
            "id": str(change.entity_id),
            "level": row.get("level"),
            "category": row.get("category"),
            "title": row.get("title"),
            "description": row.get("description"),
            "source_url": row.get("source_url"),
            "status": row.get("status"),
        }
    if change.entity_type == "passage":
        return {
            "id": str(change.entity_id),
            "exam_id": row.get("exam_id"),
            "text": row.get("content"),
        }
    if change.entity_type == "question":
        return {
            "id": str(change.entity_id),
            "exam_id": row.get("exam_id"),
            "passage_id": row.get("passage_id"),
            "question_number": row.get("question_number"),
            "question_type": row.get("question_type"),
            "question_text": row.get("question_text"),
            "options": row.get("options", []),
            "answer_index": zero_based(row.get("correct_answer"))
            if row.get("answer_status") == "verified" and row.get("correct_answer") is not None
            else None,
            "answer_verified": row.get("answer_status") == "verified"
            and row.get("correct_answer") is not None,
        }
    if change.entity_type == "ai_explanation":
        if row.get("verification_status") != "approved":
            return None
        question_id = uuid.UUID(str(row["question_id"]))
        question = db.get(Question, question_id)
        if question is None or current_content_hash(db, question) != row.get("content_hash"):
            return None
        return {
            "id": str(change.entity_id),
            "question_id": str(question_id),
            "schema_version": row.get("schema_version"),
            "explanation": row.get("explanation_json"),
            "verification_status": "approved",
        }
    if change.entity_type == "exam_attempt":
        return {
            "id": str(change.entity_id),
            "exam_id": row.get("exam_id"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "total_questions": row.get("total_questions"),
            "source": row.get("source"),
        }
    if change.entity_type == "attempt_answer":
        return {
            "id": str(change.entity_id),
            "attempt_id": row.get("attempt_id"),
            "exam_id": row.get("exam_id"),
            "question_id": row.get("question_id"),
            "question_number": row.get("question_number"),
            "selected_index": zero_based(row.get("selected_answer")),
            "correct_index": zero_based(row.get("correct_answer_snapshot")),
            "is_correct": row.get("is_correct"),
        }
    if change.entity_type == "knowledge_item":
        return {
            "id": str(change.entity_id),
            "knowledge_type": row.get("knowledge_type"),
            "jlpt_level": row.get("jlpt_level"),
            "title": row.get("title"),
            "content": row.get("content"),
            "details": row.get("details", {}),
            "status": row.get("status"),
            "merged_into_id": row.get("merged_into_id"),
            "version": row.get("version"),
            "linked_question_ids": row.get("linked_question_ids", []),
        }
    if change.entity_type == "review_item":
        return {
            "id": str(change.entity_id),
            "review_type": row.get("review_type"),
            "knowledge_id": row.get("knowledge_id"),
            "related_knowledge_id": row.get("related_knowledge_id"),
            "source_question_id": row.get("source_question_id"),
            "source_question_ids": row.get("source_question_ids", []),
            "source_explanation_id": row.get("source_explanation_id"),
            "status": row.get("status"),
            "srs_state": row.get("srs_state"),
            "step_index": row.get("step_index"),
            "interval_minutes": row.get("interval_minutes"),
            "due_at": row.get("due_at"),
            "last_reviewed_at": row.get("last_reviewed_at"),
            "review_count": row.get("review_count"),
            "lapse_count": row.get("lapse_count"),
            "algorithm_version": row.get("algorithm_version"),
            "ladder": row.get("ladder"),
            "version": row.get("version"),
        }
    if change.entity_type == "android_review_event":
        return {
            "id": str(change.entity_id),
            "request_id": row.get("request_id"),
            "item_type": row.get("item_type"),
            "item_id": row.get("item_id"),
            "rating": row.get("rating"),
            "reviewed_at": row.get("reviewed_at"),
            "interval_before_minutes": row.get("interval_before_minutes"),
            "interval_after_minutes": row.get("interval_after_minutes"),
            "due_at_after": row.get("due_at_after"),
        }
    return None


@router.get("/changes")
def changes(
    db: DB,
    device: Annotated[SyncDevice, Depends(get_device)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> DataResponse[ChangePage]:
    rows = list(
        db.scalars(
            select(SyncChange)
            .where(SyncChange.id > cursor)
            .order_by(SyncChange.id)
            .limit(limit + 1)
        )
    )
    page = rows[:limit]
    next_cursor = page[-1].id if page else cursor
    data = []
    for row in page:
        payload = _payload(db, row)
        # An explanation that became unapproved/stale must remove the previously trusted
        # mirror copy, even though the underlying row itself was updated rather than deleted.
        operation = (
            "delete" if row.entity_type == "ai_explanation" and payload is None else row.operation
        )
        data.append(
            ChangeRead(
                cursor=row.id,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                operation=operation,
                version=row.version,
                changed_at=row.changed_at,
                schema_version=row.schema_version,
                data=payload,
            )
        )
    device.last_pull_at = datetime.now(UTC)
    db.commit()
    return DataResponse(
        data=ChangePage(data=data, next_cursor=next_cursor, has_more=len(rows) > limit)
    )


@router.post("/push", status_code=status.HTTP_200_OK)
def push(
    payload: PushRequest, db: DB, device: Annotated[SyncDevice, Depends(get_device)]
) -> DataResponse[PushAck]:
    accepted: list[uuid.UUID] = []
    duplicates: list[uuid.UUID] = []
    now = datetime.now(UTC)
    for incoming in payload.events:
        if incoming.reviewed_at > now + timedelta(
            minutes=5
        ) or incoming.due_at_after > now + timedelta(days=3660):
            from app.core.errors import DomainValidationError

            raise DomainValidationError("Thời gian sự kiện vượt giới hạn cho phép.")
        inserted = db.execute(
            pg_insert(AndroidReviewEvent)
            .values(
                id=uuid.uuid4(),
                request_id=incoming.request_id,
                device_id=device.id,
                item_type=incoming.item_type,
                item_id=incoming.item_id,
                rating=incoming.rating,
                reviewed_at=incoming.reviewed_at,
                interval_before_minutes=incoming.interval_before_minutes,
                interval_after_minutes=incoming.interval_after_minutes,
                due_at_after=incoming.due_at_after,
            )
            .on_conflict_do_nothing(index_elements=[AndroidReviewEvent.request_id])
            .returning(AndroidReviewEvent.request_id)
        ).scalar_one_or_none()
        if inserted is None:
            existing = db.scalar(
                select(AndroidReviewEvent)
                .where(AndroidReviewEvent.request_id == incoming.request_id)
                .with_for_update()
            )
            if existing is None:
                raise RuntimeError("Conflicting sync event disappeared before idempotency check.")
            if existing.device_id != device.id or (
                existing.item_type,
                existing.item_id,
                existing.rating,
                existing.reviewed_at,
                existing.interval_before_minutes,
                existing.interval_after_minutes,
                existing.due_at_after,
            ) != (
                incoming.item_type,
                incoming.item_id,
                incoming.rating,
                incoming.reviewed_at,
                incoming.interval_before_minutes,
                incoming.interval_after_minutes,
                incoming.due_at_after,
            ):
                from app.core.errors import ConflictError

                raise ConflictError("request_id đã được dùng cho sự kiện khác.")
            duplicates.append(incoming.request_id)
            continue
        accepted.append(incoming.request_id)
    if payload.events:
        device.last_push_at = now
    db.commit()
    return DataResponse(data=PushAck(accepted=accepted, duplicates=duplicates))
