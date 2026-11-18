from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import API_VERSION, get_settings
from app.core.responses import DataResponse
from app.database.session import get_db

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    environment: str
    version: str


@router.get(
    "/health",
    summary="Liveness + database connectivity",
    response_model=DataResponse[HealthStatus],
    responses={503: {"model": DataResponse[HealthStatus], "description": "Database unavailable"}},
)
def health(db: Annotated[Session, Depends(get_db)]) -> object:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        body: DataResponse[HealthStatus] = DataResponse(
            data=HealthStatus(
                status="degraded",
                database="unavailable",
                environment=settings.app_env,
                version=API_VERSION,
            )
        )
        return JSONResponse(status_code=503, content=body.model_dump())
    return DataResponse(
        data=HealthStatus(
            status="ok", database="ok", environment=settings.app_env, version=API_VERSION
        )
    )
