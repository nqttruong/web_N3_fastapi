import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DomainValidationError
from app.core.extension_auth import verify_extension_request
from app.core.ratelimit import import_rate_limit
from app.core.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PageMeta,
    PageParams,
    PageResponse,
    page_params,
)
from app.core.schemas import HttpUrlStr
from app.core.security import get_principal
from app.database.enums import ExamCategory, ImportStatus
from app.database.session import get_db
from app.imports import service
from app.imports.browser_capture import BrowserCapture
from app.imports.schemas import (
    CommitRequest,
    CommitResult,
    DraftListItem,
    DraftRead,
    DraftUpdate,
    HtmlImportCreate,
    ImportCapabilities,
    ReparseRequest,
    TextImportCreate,
)

DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
RateLimited = [Depends(import_rate_limit)]

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    dependencies=[Depends(get_principal)],
    responses={
        **ERROR_RESPONSES,
        413: {"description": "Payload too large"},
        429: {"description": "Rate limited"},
    },
)

_url_adapter: TypeAdapter[str] = TypeAdapter(HttpUrlStr)


@router.get("/capabilities", summary="OCR availability and upload limits")
def get_capabilities(settings: Config) -> DataResponse[ImportCapabilities]:
    return DataResponse(data=service.capabilities(settings))


@router.get("", summary="List import drafts (newest first)")
def list_drafts(
    db: DB,
    page: Annotated[PageParams, Depends(page_params)],
    draft_status: Annotated[ImportStatus | None, Query(alias="status")] = None,
) -> PageResponse[DraftListItem]:
    items, total = service.list_drafts(db, page, draft_status)
    return PageResponse(data=items, meta=PageMeta.build(page, total))


@router.post(
    "/text",
    status_code=status.HTTP_201_CREATED,
    dependencies=RateLimited,
    summary="Mode A — parse pasted text into a draft (nothing is saved to exams yet)",
)
def import_text(payload: TextImportCreate, db: DB, settings: Config) -> DataResponse[DraftRead]:
    return DataResponse(data=service.create_from_text(db, settings, payload))


@router.post(
    "/html",
    status_code=status.HTTP_201_CREATED,
    dependencies=RateLimited,
    summary="Mode B — parse pasted HTML into a draft (no JS executed, nothing fetched)",
)
def import_html(payload: HtmlImportCreate, db: DB, settings: Config) -> DataResponse[DraftRead]:
    return DataResponse(data=service.create_from_html(db, settings, payload))


@router.post(
    "/browser-capture",
    status_code=status.HTTP_201_CREATED,
    dependencies=RateLimited,
    summary="Create an editable import draft from the authenticated local Chrome extension",
    responses={
        401: {"description": "Invalid extension token or non-local peer"},
        413: {"description": "Payload too large"},
        503: {"description": "Extension capture is disabled"},
    },
)
async def import_browser_capture(
    request: Request,
    db: DB,
    settings: Config,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> DataResponse[DraftRead]:
    # The peer address plus a shared bearer secret authenticate this local-only route. Origin and
    # source_url are metadata/validation only, never proof that a caller is the extension.
    verify_extension_request(request, settings, authorization)
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > settings.import_max_html_bytes:
                raise service.PayloadTooLargeError(
                    "Capture vượt quá giới hạn kích thước.",
                    details={"limit": settings.import_max_html_bytes},
                )
        except ValueError:
            raise DomainValidationError("Content-Length không hợp lệ.") from None
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > settings.import_max_html_bytes:
            raise service.PayloadTooLargeError(
                "Capture vượt quá giới hạn kích thước.",
                details={"limit": settings.import_max_html_bytes},
            )
        chunks.append(chunk)
    body = b"".join(chunks)
    try:
        payload = BrowserCapture.model_validate_json(body)
    except ValidationError as exc:
        details = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors(include_url=False)
        ]
        raise DomainValidationError("Capture không đúng schema.", details=details) from exc
    draft, created = service.create_from_browser_capture(db, settings, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return DataResponse(data=draft)


@router.post(
    "/images",
    status_code=status.HTTP_201_CREATED,
    dependencies=RateLimited,
    summary="Mode C — upload screenshots (PNG/JPEG/WEBP), run local OCR, create a draft",
    responses={503: {"description": "OCR engine not available"}},
)
def import_images(
    request: Request,
    db: DB,
    settings: Config,
    files: Annotated[list[UploadFile], File(description="Screenshots in reading order")],
    source_url: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form(max_length=300)] = None,
    category: Annotated[ExamCategory | None, Form()] = None,
) -> DataResponse[DraftRead]:
    declared = int(request.headers.get("content-length") or 0)
    hard_limit = settings.import_max_images * settings.import_max_image_bytes + 1_000_000
    if declared > hard_limit:
        raise service.PayloadTooLargeError(
            "Tổng dung lượng tải lên quá lớn.", details={"limit": hard_limit}
        )
    url: str | None = None
    if source_url and source_url.strip():
        try:
            url = _url_adapter.validate_python(source_url)
        except ValidationError as exc:
            raise DomainValidationError(
                "URL nguồn không hợp lệ.", details={"field": "source_url"}
            ) from exc
    if len(files) > settings.import_max_images:
        raise DomainValidationError(
            f"Tối đa {settings.import_max_images} ảnh mỗi lần.",
            details={"limit": settings.import_max_images},
        )
    uploads: list[service.UploadedFile] = []
    for f in files:
        data = f.file.read(settings.import_max_image_bytes + 1)
        uploads.append(service.UploadedFile(filename=f.filename or "image", data=data))
    return DataResponse(
        data=service.create_from_images(
            db, settings, uploads, source_url=url, title=title, category=category
        )
    )


@router.get("/{draft_id}", summary="Get a draft with preview content, issues and summary")
def get_draft(draft_id: uuid.UUID, db: DB) -> DataResponse[DraftRead]:
    return DataResponse(data=service.get_draft(db, draft_id))


@router.patch("/{draft_id}", summary="Save edits (optimistic locking via `version`)")
def update_draft(draft_id: uuid.UUID, payload: DraftUpdate, db: DB) -> DataResponse[DraftRead]:
    return DataResponse(data=service.update_draft(db, draft_id, payload))


@router.post(
    "/{draft_id}/parse",
    dependencies=RateLimited,
    summary="Re-run the parser (optionally on corrected raw text/HTML); replaces question edits",
)
def reparse_draft(
    draft_id: uuid.UUID, payload: ReparseRequest, db: DB, settings: Config
) -> DataResponse[DraftRead]:
    return DataResponse(data=service.reparse(db, settings, draft_id, payload))


@router.post("/{draft_id}/validate", summary="Re-run validation and duplicate detection")
def validate_draft(draft_id: uuid.UUID, db: DB) -> DataResponse[DraftRead]:
    return DataResponse(data=service.validate(db, draft_id))


@router.post(
    "/{draft_id}/commit",
    summary="Save the draft as an exam (+ optional attempt) in one transaction; idempotent",
)
def commit_draft(
    draft_id: uuid.UUID, payload: CommitRequest, db: DB, response: Response
) -> DataResponse[CommitResult]:
    result = service.commit(db, draft_id, payload)
    response.status_code = (
        status.HTTP_200_OK if result.already_committed else status.HTTP_201_CREATED
    )
    return DataResponse(data=result)


@router.delete(
    "/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a draft and its uploaded files (a committed exam is kept)",
)
def delete_draft(draft_id: uuid.UUID, db: DB, settings: Config) -> Response:
    service.delete_draft(db, settings, draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{draft_id}/assets/{asset_id}",
    summary="Normalised screenshot (PNG) for side-by-side review",
    response_class=FileResponse,
)
def get_asset(draft_id: uuid.UUID, asset_id: uuid.UUID, db: DB, settings: Config) -> FileResponse:
    path = service.asset_path(db, settings, draft_id, asset_id)
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{asset_id}.png"',
            "Cache-Control": "private, max-age=300",
        },
    )
