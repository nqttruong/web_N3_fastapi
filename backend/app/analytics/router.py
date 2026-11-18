import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import weakness
from app.analytics.schemas import DashboardSummary
from app.analytics.service import dashboard_summary, jlpt_report, knowledge_report, weakness_report
from app.core.responses import DataResponse
from app.core.security import get_principal
from app.database.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_principal)])


@router.get("/summary", summary="Dashboard totals computed from stored data")
def summary(db: Annotated[Session, Depends(get_db)]) -> DataResponse[DashboardSummary]:
    return DataResponse(data=dashboard_summary(db))


@router.get("/jlpt", summary="JLPT mock exam analytics from stored attempts")
def jlpt_analytics(db: Annotated[Session, Depends(get_db)]) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=jlpt_report(db))


@router.get("/weaknesses", summary="Weakness analytics from real attempts and reviews")
def weaknesses(
    db: Annotated[Session, Depends(get_db)],
    window: Annotated[str, Query(pattern="^(7d|30d|all)$")] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=weakness_report(db, window, limit))


@router.get("/knowledge/{knowledge_id}", summary="Analytics of one knowledge item")
def knowledge_analytics(
    knowledge_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]
) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=knowledge_report(db, knowledge_id))


@router.get("/review-progress", summary="Review activity, ratings and answer accuracy")
def review_progress(
    db: Annotated[Session, Depends(get_db)], days: Annotated[int, Query(ge=1, le=365)] = 30
) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=weakness.review_progress(db, days))
