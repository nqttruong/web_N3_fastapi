import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import ERROR_RESPONSES, DataResponse
from app.core.security import get_principal
from app.database.enums import KnowledgeType
from app.database.session import get_db
from app.knowledge import normalize, service
from app.knowledge.schemas import (
    ConfirmRequest,
    ConfirmResult,
    ExtractRequest,
    ExtractResult,
    KnowledgeDetail,
    KnowledgeListItem,
    KnowledgeUpdate,
    MergeRequest,
    QuestionExtractionRead,
    RelationCreate,
    SplitRequest,
)

DB = Annotated[Session, Depends(get_db)]
router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(get_principal)],
    responses=ERROR_RESPONSES,
)


@router.get("", summary="Knowledge items with stats and review priority")
def list_knowledge(
    db: DB,
    knowledge_type: Annotated[KnowledgeType | None, Query(alias="type")] = None,
    status: Annotated[str, Query(pattern="^(active|archived|merged|all)$")] = "active",
    q: Annotated[str | None, Query(max_length=100)] = None,
    priority: Annotated[
        str | None, Query(pattern="^(review_now|due_soon|stable|insufficient_data)$")
    ] = None,
) -> DataResponse[list[KnowledgeListItem]]:
    return DataResponse(
        data=service.list_knowledge(
            db, knowledge_type=knowledge_type, status=status, q=q, priority=priority
        )
    )


@router.post(
    "/extract",
    summary="Preview knowledge candidates from APPROVED, current explanations (no writes)",
)
def extract(payload: ExtractRequest, db: DB) -> DataResponse[ExtractResult]:
    results = service.extract(db, payload.question_ids, payload.attempt_id)
    return DataResponse(
        data=ExtractResult(
            questions=[
                QuestionExtractionRead.model_validate(r, from_attributes=True) for r in results
            ],
            reading_skills=normalize.READING_SKILLS,
        )
    )


@router.post("/confirm", summary="Persist confirmed candidates + create review items (idempotent)")
def confirm(payload: ConfirmRequest, db: DB) -> DataResponse[ConfirmResult]:
    return DataResponse(data=service.confirm(db, payload))


@router.post("/merge", summary="Merge items into a target (history kept, sources marked merged)")
def merge(payload: MergeRequest, db: DB) -> DataResponse[KnowledgeDetail]:
    return DataResponse(data=service.merge(db, payload.target_id, payload.source_ids))


@router.get(
    "/{knowledge_id}", summary="Knowledge detail: questions, mistakes, relations, evidence, reviews"
)
def detail(knowledge_id: uuid.UUID, db: DB) -> DataResponse[KnowledgeDetail]:
    return DataResponse(data=service.detail(db, knowledge_id))


@router.patch(
    "/{knowledge_id}", summary="Edit label/summary/details or archive (optimistic locking)"
)
def update(
    knowledge_id: uuid.UUID, payload: KnowledgeUpdate, db: DB
) -> DataResponse[KnowledgeDetail]:
    return DataResponse(data=service.update_knowledge(db, knowledge_id, payload))


@router.post("/{knowledge_id}/split", summary="Move some questions to a new sense of this item")
def split(knowledge_id: uuid.UUID, payload: SplitRequest, db: DB) -> DataResponse[KnowledgeDetail]:
    return DataResponse(
        data=service.split(db, knowledge_id, payload.title, payload.content, payload.question_ids)
    )


@router.post("/{knowledge_id}/relations", summary="Add confused_with / prerequisite / related_to")
def add_relation(
    knowledge_id: uuid.UUID, payload: RelationCreate, db: DB
) -> DataResponse[KnowledgeDetail]:
    return DataResponse(
        data=service.create_relation(db, knowledge_id, payload.target_id, payload.relation_type)
    )
