import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.ratelimit import import_rate_limit
from app.core.responses import ERROR_RESPONSES, DataResponse
from app.core.security import get_principal
from app.database.enums import PracticeStatus
from app.database.session import get_db
from app.practice import service
from app.practice.schemas import (
    ExportRequest,
    ExportResult,
    GenerateRequest,
    GenerationRead,
    ManualImportRequest,
    ManualImportResult,
    PracticeQuestionRead,
    ReviewRequest,
)

DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
router = APIRouter(
    prefix="/practice",
    tags=["practice"],
    dependencies=[Depends(get_principal)],
    responses=ERROR_RESPONSES,
)


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(import_rate_limit)],
    summary="Generate practice questions with the AI provider (saved as needs_review)",
)
def generate(payload: GenerateRequest, db: DB, settings: Config) -> DataResponse[GenerationRead]:
    return DataResponse(
        data=service.generate(
            db, settings, payload.knowledge_id, payload.count, payload.question_type
        )
    )


@router.get(
    "/generation-jobs/{generation_id}",
    summary="A generation (processed synchronously) and its questions",
)
def get_generation(generation_id: uuid.UUID, db: DB) -> DataResponse[GenerationRead]:
    return DataResponse(data=service.get_generation(db, generation_id))


@router.post("/export-prompt", summary="Manual mode: prompt for ChatGPT")
def export_prompt(payload: ExportRequest, db: DB) -> DataResponse[ExportResult]:
    return DataResponse(
        data=service.export_prompt(db, payload.knowledge_id, payload.count, payload.question_type)
    )


@router.post(
    "/manual-import", summary="Manual mode: validate (save=false) or save JSON from ChatGPT"
)
def manual_import(
    payload: ManualImportRequest, db: DB, response: Response
) -> DataResponse[ManualImportResult]:
    result = service.manual_import(
        db,
        payload.knowledge_id,
        payload.count,
        payload.raw_json,
        save=payload.save,
        model_label=payload.model_label,
    )
    response.status_code = status.HTTP_201_CREATED if payload.save else status.HTTP_200_OK
    return DataResponse(data=result)


@router.get("", summary="Practice questions (filter by knowledge / status)")
def list_questions(
    db: DB,
    knowledge_id: uuid.UUID | None = None,
    practice_status: Annotated[PracticeStatus | None, Query(alias="status")] = None,
) -> DataResponse[list[PracticeQuestionRead]]:
    return DataResponse(data=service.list_questions(db, knowledge_id, practice_status))


@router.post("/{question_id}/approve", summary="User approves the question and its proposed answer")
def approve(
    question_id: uuid.UUID, payload: ReviewRequest, db: DB
) -> DataResponse[PracticeQuestionRead]:
    return DataResponse(data=service.review(db, question_id, PracticeStatus.APPROVED, payload.note))


@router.post("/{question_id}/reject", summary="User rejects the question")
def reject(
    question_id: uuid.UUID, payload: ReviewRequest, db: DB
) -> DataResponse[PracticeQuestionRead]:
    return DataResponse(data=service.review(db, question_id, PracticeStatus.REJECTED, payload.note))
