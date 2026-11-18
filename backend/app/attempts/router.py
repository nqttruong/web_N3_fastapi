import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.attempts import service
from app.attempts.schemas import AttemptCreate, AttemptDetail, AttemptSummary, MistakeRead
from app.core.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PageMeta,
    PageParams,
    PageResponse,
    page_params,
)
from app.core.security import get_principal
from app.database.session import get_db

DB = Annotated[Session, Depends(get_db)]

router = APIRouter(
    prefix="/attempts",
    tags=["attempts"],
    dependencies=[Depends(get_principal)],
    responses=ERROR_RESPONSES,
)


@router.get("", summary="List attempts (newest first)")
def list_attempts(
    db: DB,
    page: Annotated[PageParams, Depends(page_params)],
    exam_id: uuid.UUID | None = None,
) -> PageResponse[AttemptSummary]:
    items, total = service.list_attempts(db, page, exam_id)
    return PageResponse(data=items, meta=PageMeta.build(page, total))


@router.get("/mistakes", summary="List wrong questions aggregated from graded attempts")
def list_mistakes(
    db: DB,
    page: Annotated[PageParams, Depends(page_params)],
    exam_id: uuid.UUID | None = None,
    skill: Annotated[str | None, Query(pattern="^(vocabulary|kanji|grammar|reading)$")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> PageResponse[MistakeRead]:
    items, total = service.list_mistakes(db, page, exam_id=exam_id, skill=skill, q=q)
    return PageResponse(data=items, meta=PageMeta.build(page, total))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a completed attempt; the server grades it",
)
def create_attempt(payload: AttemptCreate, db: DB) -> DataResponse[AttemptDetail]:
    return DataResponse(data=service.create_attempt(db, payload))


@router.get("/{attempt_id}", summary="Get attempt with per-question results")
def get_attempt(attempt_id: uuid.UUID, db: DB) -> DataResponse[AttemptDetail]:
    return DataResponse(data=service.get_attempt(db, attempt_id))
