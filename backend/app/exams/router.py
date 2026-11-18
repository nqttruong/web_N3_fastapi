import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PageMeta,
    PageParams,
    PageResponse,
    page_params,
)
from app.core.security import get_principal
from app.database.enums import ExamCategory, ExamStatus, JlptLevel
from app.database.session import get_db
from app.exams import service
from app.exams.schemas import (
    ExamCreate,
    ExamListFilters,
    ExamRead,
    ExamSourceCreate,
    ExamSourceRead,
    ExamUpdate,
    PassageCreate,
    PassageRead,
    QuestionCreate,
    QuestionRead,
    QuestionUpdate,
)

DB = Annotated[Session, Depends(get_db)]
Page = Annotated[PageParams, Depends(page_params)]

router = APIRouter(dependencies=[Depends(get_principal)], responses=ERROR_RESPONSES)


def _question_read(question: object, *, include_answers: bool = True) -> QuestionRead:
    read = QuestionRead.model_validate(question)
    if not include_answers:
        read = read.model_copy(update={"correct_answer": None, "answer_source": None})
    return read


# ------------------------------------------------------------------ sources
@router.get("/exam-sources", tags=["exam-sources"], summary="List exam sources")
def list_sources(db: DB) -> DataResponse[list[ExamSourceRead]]:
    return DataResponse(data=[ExamSourceRead.model_validate(s) for s in service.list_sources(db)])


@router.post(
    "/exam-sources",
    tags=["exam-sources"],
    status_code=status.HTTP_201_CREATED,
    summary="Register an exam source (metadata only; nothing is fetched)",
)
def create_source(payload: ExamSourceCreate, db: DB) -> DataResponse[ExamSourceRead]:
    return DataResponse(data=ExamSourceRead.model_validate(service.create_source(db, payload)))


# -------------------------------------------------------------------- exams
@router.get("/exams", tags=["exams"], summary="List exams (search, filter, paginate)")
def list_exams(
    db: DB,
    page: Page,
    q: Annotated[str | None, Query(max_length=200, description="Search title/description")] = None,
    category: ExamCategory | None = None,
    exam_status: Annotated[ExamStatus | None, Query(alias="status")] = None,
    level: JlptLevel | None = None,
) -> PageResponse[ExamRead]:
    filters = ExamListFilters(
        q=q.strip() if q and q.strip() else None, category=category, status=exam_status, level=level
    )
    items, total = service.list_exams(db, filters, page)
    return PageResponse(data=items, meta=PageMeta.build(page, total))


@router.post("/exams", tags=["exams"], status_code=status.HTTP_201_CREATED, summary="Create exam")
def create_exam(payload: ExamCreate, db: DB) -> DataResponse[ExamRead]:
    return DataResponse(data=service.create_exam(db, payload))


@router.get("/exams/{exam_id}", tags=["exams"], summary="Get exam")
def get_exam(exam_id: uuid.UUID, db: DB) -> DataResponse[ExamRead]:
    return DataResponse(data=service.get_exam(db, exam_id))


@router.patch("/exams/{exam_id}", tags=["exams"], summary="Partially update exam")
def update_exam(exam_id: uuid.UUID, payload: ExamUpdate, db: DB) -> DataResponse[ExamRead]:
    return DataResponse(data=service.update_exam(db, exam_id, payload))


# ----------------------------------------------------------------- passages
@router.get("/exams/{exam_id}/passages", tags=["passages"], summary="List passages of an exam")
def list_passages(exam_id: uuid.UUID, db: DB) -> DataResponse[list[PassageRead]]:
    return DataResponse(
        data=[PassageRead.model_validate(p) for p in service.list_passages(db, exam_id)]
    )


@router.post(
    "/exams/{exam_id}/passages",
    tags=["passages"],
    status_code=status.HTTP_201_CREATED,
    summary="Add a reading passage to an exam",
)
def create_passage(exam_id: uuid.UUID, payload: PassageCreate, db: DB) -> DataResponse[PassageRead]:
    return DataResponse(
        data=PassageRead.model_validate(service.create_passage(db, exam_id, payload))
    )


# ---------------------------------------------------------------- questions
@router.get("/exams/{exam_id}/questions", tags=["questions"], summary="List questions of an exam")
def list_questions(
    exam_id: uuid.UUID,
    db: DB,
    page: Page,
    include_answers: Annotated[
        bool, Query(description="false hides correct_answer (practice mode)")
    ] = True,
) -> PageResponse[QuestionRead]:
    items, total = service.list_questions(db, exam_id, page)
    return PageResponse(
        data=[_question_read(q, include_answers=include_answers) for q in items],
        meta=PageMeta.build(page, total),
    )


@router.post(
    "/exams/{exam_id}/questions",
    tags=["questions"],
    status_code=status.HTTP_201_CREATED,
    summary="Add a question to an exam",
)
def create_question(
    exam_id: uuid.UUID, payload: QuestionCreate, db: DB
) -> DataResponse[QuestionRead]:
    return DataResponse(data=_question_read(service.create_question(db, exam_id, payload)))


@router.get("/questions/{question_id}", tags=["questions"], summary="Get one question")
def get_question(question_id: uuid.UUID, db: DB) -> DataResponse[QuestionRead]:
    return DataResponse(data=_question_read(service.get_question_model(db, question_id)))


@router.patch("/questions/{question_id}", tags=["questions"], summary="Partially update question")
def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, db: DB
) -> DataResponse[QuestionRead]:
    return DataResponse(data=_question_read(service.update_question(db, question_id, payload)))


@router.delete(
    "/questions/{question_id}",
    tags=["questions"],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question that has never been answered in an attempt",
)
def delete_question(question_id: uuid.UUID, db: DB) -> Response:
    service.delete_question(db, question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
