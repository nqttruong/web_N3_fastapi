import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.responses import DataResponse
from app.core.security import get_principal
from app.database.session import get_db
from app.learning_content import service
from app.learning_content.schemas import LearningItemPage, LearningSyncStatus, SyncQueued
from app.learning_content.source import ITEM_TYPES

DB = Annotated[Session, Depends(get_db)]
router = APIRouter(
    prefix="/learning-content",
    tags=["learning-content"],
    dependencies=[Depends(get_principal)],
)


@router.get("/sync/status", summary="Source versions and latest learning content sync state")
def sync_status(
    db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> DataResponse[LearningSyncStatus]:
    return DataResponse(data=service.sync_status(db, settings))


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED, summary="Queue a safe source check")
def request_sync(
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    sync_token: Annotated[str | None, Header(alias="X-Learning-Sync-Token")] = None,
) -> DataResponse[SyncQueued]:
    source_dir = settings.android_learning_source_dir
    if source_dir is None or not source_dir.is_dir():
        raise HTTPException(status_code=503, detail="Android learning source is unavailable")
    expected = settings.learning_content_sync_token
    if settings.app_env == "production" and expected is None:
        raise HTTPException(
            status_code=503, detail="Manual sync is disabled until a sync token is configured"
        )
    if expected is not None and not hmac.compare_digest(
        sync_token or "", expected.get_secret_value()
    ):
        raise HTTPException(status_code=401, detail="Invalid learning sync credential")
    run = service.enqueue_sync(db, "manual")
    return DataResponse(
        data=SyncQueued(
            run_id=run.id,
            status=run.status,
            message="Đã đưa yêu cầu kiểm tra vào hàng đợi sync worker.",
        )
    )


@router.get("/items", summary="Paginated licensed Android vocabulary, kanji and grammar")
def list_learning_items(
    db: DB,
    item_type: Annotated[str | None, Query(alias="type")] = None,
    jlpt_level: Annotated[str | None, Query(pattern="^N[1-5]$")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> DataResponse[LearningItemPage]:
    if item_type is not None and item_type not in ITEM_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported learning content type")
    return DataResponse(
        data=service.learning_items(
            db,
            item_type=item_type,
            jlpt_level=jlpt_level,
            q=q,
            page=page,
            page_size=page_size,
        )
    )
