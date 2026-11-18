import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.ratelimit import import_rate_limit
from app.core.responses import ERROR_RESPONSES, DataResponse
from app.core.security import get_principal
from app.database.enums import VerificationStatus
from app.database.session import get_db
from app.explanations import jobs, service
from app.explanations.context import Ineligible, build_context
from app.explanations.schemas import (
    AttemptOverview,
    BatchRequest,
    Capabilities,
    ExplanationRead,
    ExportPromptRequest,
    ExportPromptResult,
    GenerateRequest,
    GenerateResult,
    JobRead,
    ManualImportRequest,
    ManualImportResult,
    OverviewItem,
    QuestionExplanations,
    ReviewRequest,
)

DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]

router = APIRouter(
    tags=["explanations"],
    dependencies=[Depends(get_principal)],
    responses={
        **ERROR_RESPONSES,
        429: {"description": "Rate limited / AI budget exceeded"},
        502: {"description": "AI provider error or invalid AI output"},
        503: {"description": "AI not configured — use manual mode"},
    },
)


@router.get("/explanations/capabilities", summary="AI availability, versions, budget usage")
def get_capabilities(db: DB, settings: Config) -> DataResponse[Capabilities]:
    return DataResponse(data=service.capabilities(db, settings))


@router.post(
    "/explanations/generate",
    summary="Explain one question via the AI provider (returns a cached one unless force=true)",
    dependencies=[Depends(import_rate_limit)],
)
def generate(
    payload: GenerateRequest, db: DB, settings: Config, response: Response
) -> DataResponse[GenerateResult]:
    outcome = service.generate_for_question(
        db, settings, payload.question_id,
        force=payload.force, attempt_answer_id=payload.attempt_answer_id,
    )  # fmt: skip
    response.status_code = (
        status.HTTP_201_CREATED if outcome.kind == "generated" else status.HTTP_200_OK
    )
    return DataResponse(data=service.generate_result(db, outcome))


@router.post(
    "/explanations/batch",
    summary="Queue explanations for an attempt's wrong answers (idempotent)",
    dependencies=[Depends(import_rate_limit)],
)
def batch(
    payload: BatchRequest,
    db: DB,
    settings: Config,
    response: Response,
    idempotency_key: Annotated[str | None, Header(max_length=200)] = None,
) -> DataResponse[JobRead]:
    job, created = jobs.create_batch(
        db, settings, payload.attempt_id, payload.question_ids,
        force=payload.force, idempotency_key=idempotency_key,
    )  # fmt: skip
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return DataResponse(data=jobs.to_read(db, job))


@router.get("/explanations/jobs/{job_id}", summary="Job progress (poll this)")
def get_job(job_id: uuid.UUID, db: DB) -> DataResponse[JobRead]:
    return DataResponse(data=jobs.to_read(db, jobs.get_job(db, job_id)))


@router.post("/explanations/jobs/{job_id}/retry", summary="Re-queue failed/cancelled items")
def retry_job(job_id: uuid.UUID, db: DB, settings: Config) -> DataResponse[JobRead]:
    return DataResponse(data=jobs.to_read(db, jobs.retry_job(db, settings, job_id)))


@router.post("/explanations/jobs/{job_id}/cancel", summary="Cancel pending items")
def cancel_job(job_id: uuid.UUID, db: DB) -> DataResponse[JobRead]:
    return DataResponse(data=jobs.to_read(db, jobs.cancel_job(db, job_id)))


@router.get(
    "/attempts/{attempt_id}/explanations",
    summary="Per-answer explanation status for an attempt + latest job (survives reloads)",
)
def attempt_overview(attempt_id: uuid.UUID, db: DB) -> DataResponse[AttemptOverview]:
    rows = service.attempt_answers(db, attempt_id)
    items: list[OverviewItem] = []
    for answer, question in rows:
        ctx = build_context(db, question.id)
        current = None
        if not isinstance(ctx, Ineligible):
            current = service.find_current(db, question.id, ctx.content_hash)
        items.append(
            OverviewItem(
                attempt_answer_id=answer.id,
                question_id=question.id,
                question_number=answer.question_number,
                selected_answer=answer.selected_answer,
                is_correct=answer.is_correct,
                eligible=not isinstance(ctx, Ineligible),
                ineligible_code=ctx.code if isinstance(ctx, Ineligible) else None,
                explanation_id=current.id if current else None,
                explanation_status=VerificationStatus(current.verification_status)
                if current
                else None,
            )
        )
    wrong = [i for i in items if i.is_correct is False]
    latest = jobs.latest_for_attempt(db, attempt_id)
    return DataResponse(
        data=AttemptOverview(
            attempt_id=attempt_id,
            wrong_count=len(wrong),
            eligible_wrong_count=sum(i.eligible for i in wrong),
            explained_wrong_count=sum(i.explanation_id is not None for i in wrong),
            needs_review_count=sum(
                i.explanation_status
                in {VerificationStatus.GENERATED, VerificationStatus.NEEDS_REVIEW}
                for i in wrong
            ),
            items=items,
            latest_job=jobs.to_read(db, latest) if latest else None,
        )
    )


@router.get(
    "/questions/{question_id}/explanations",
    summary="All explanation versions of a question (stale ones flagged) + current id",
)
def question_explanations(
    question_id: uuid.UUID,
    db: DB,
    attempt_answer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> DataResponse[QuestionExplanations]:
    return DataResponse(data=service.question_explanations(db, question_id, attempt_answer_id))


@router.get("/explanations/{explanation_id}", summary="One explanation")
def get_explanation(
    explanation_id: uuid.UUID,
    db: DB,
    attempt_answer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> DataResponse[ExplanationRead]:
    return DataResponse(data=service.get_explanation(db, explanation_id, attempt_answer_id))


@router.post("/explanations/{explanation_id}/approve", summary="User confirms the explanation")
def approve(
    explanation_id: uuid.UUID, payload: ReviewRequest, db: DB
) -> DataResponse[ExplanationRead]:
    return DataResponse(data=service.approve(db, explanation_id, payload.note))


@router.post("/explanations/{explanation_id}/reject", summary="User marks it inaccurate")
def reject(
    explanation_id: uuid.UUID, payload: ReviewRequest, db: DB
) -> DataResponse[ExplanationRead]:
    return DataResponse(data=service.reject(db, explanation_id, payload.note))


@router.post("/explanations/export-prompt", summary="Manual mode: prompt to paste into ChatGPT")
def export_prompt(payload: ExportPromptRequest, db: DB) -> DataResponse[ExportPromptResult]:
    return DataResponse(data=service.export_prompt(db, payload.question_ids, payload.attempt_id))


@router.post(
    "/explanations/manual-import",
    summary="Manual mode: validate (save=false) or save (save=true) JSON pasted back from ChatGPT",
)
def manual_import(
    payload: ManualImportRequest, db: DB, response: Response
) -> DataResponse[ManualImportResult]:
    result = service.manual_import(
        db,
        payload.question_ids,
        payload.raw_json,
        save=payload.save,
        model_label=payload.model_label,
    )
    response.status_code = status.HTTP_201_CREATED if payload.save else status.HTTP_200_OK
    return DataResponse(data=result)
