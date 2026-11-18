"""Import pipeline orchestration.

    input → size/type validation → adapter (parse) → normalisation (provenance) →
    structural validation → duplicate detection → preview (draft) → user edits/confirms →
    commit (one transaction, idempotent)

Nothing reaches ``exams``/``questions``/``exam_attempts`` before ``commit``.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.attempts.models import ExamAttempt
from app.attempts.service import build_graded_attempt, check_attempt_times
from app.core.config import Settings
from app.core.errors import AppError, ConflictError, DomainValidationError, NotFoundError
from app.core.responses import PageParams
from app.core.time import utcnow
from app.database.enums import (
    AnswerSource,
    AnswerStatus,
    AttemptSource,
    ExamStatus,
    ImportMethod,
    ImportStatus,
    OcrStatus,
    QuestionType,
)
from app.exams.fingerprints import question_content_hash, question_fingerprint
from app.exams.models import Exam, Passage, Question
from app.imports import images, storage
from app.imports.adapters.base import ParseResult, UnsupportedInputError
from app.imports.adapters.html import canonical_url, parse_html
from app.imports.adapters.text import GenericTextAdapter
from app.imports.browser_capture import BrowserCapture
from app.imports.duplicates import duplicate_issues
from app.imports.models import IMAGE_MIME_TYPES, ImportAsset, ImportDraft
from app.imports.ocr import OcrError, get_engine
from app.imports.schemas import (
    AssetRead,
    CommitRequest,
    CommitResult,
    DraftAttempt,
    DraftContent,
    DraftExam,
    DraftListItem,
    DraftPassage,
    DraftQuestion,
    DraftRead,
    DraftUpdate,
    HtmlImportCreate,
    ImportCapabilities,
    ImportLimits,
    Issue,
    OcrCapability,
    ParserNote,
    ReparseRequest,
    TextImportCreate,
)
from app.imports.textutil import category_for_types, guess_question_type
from app.imports.validation import derive_answer_sources, structural_issues, summarize

logger = logging.getLogger(__name__)


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "payload_too_large"


class OcrUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "ocr_unavailable"


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    data: bytes


# ------------------------------------------------------------------ capabilities
def capabilities(settings: Settings) -> ImportCapabilities:
    av = get_engine(settings).availability()
    return ImportCapabilities(
        ocr=OcrCapability(
            available=av.available, engine=av.engine, languages=av.languages, reason=av.reason
        ),
        limits=ImportLimits(
            max_text_chars=settings.import_max_text_chars,
            max_html_bytes=settings.import_max_html_bytes,
            max_images=settings.import_max_images,
            max_image_bytes=settings.import_max_image_bytes,
            max_image_pixels=settings.import_max_image_pixels,
            accepted_image_types=list(IMAGE_MIME_TYPES),
        ),
        adapters=[
            "generic_text",
            "generic_html",
            "dethitiengnhat_html",
            "dethitiengnhat_capture",
            "ocr_text",
        ],
    )


# ------------------------------------------------------------------ helpers
def _sha(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _check_text_size(settings: Settings, method: ImportMethod, raw: str) -> None:
    if method == ImportMethod.TEXT and len(raw) > settings.import_max_text_chars:
        raise PayloadTooLargeError(
            f"Văn bản vượt quá {settings.import_max_text_chars:,} ký tự.",
            details={"limit": settings.import_max_text_chars},
        )
    if method == ImportMethod.HTML and len(raw.encode("utf-8")) > settings.import_max_html_bytes:
        raise PayloadTooLargeError(
            f"HTML vượt quá {settings.import_max_html_bytes:,} byte.",
            details={"limit": settings.import_max_html_bytes},
        )


def _run_adapter(method: ImportMethod, raw: str, source_url: str | None) -> ParseResult:
    if method == ImportMethod.TEXT:
        return GenericTextAdapter().parse(raw)
    if method == ImportMethod.HTML:
        return parse_html(raw, source_url)
    return GenericTextAdapter(name="ocr_text", from_ocr=True).parse(raw)


def _apply_result(
    draft: ImportDraft,
    result: ParseResult,
    *,
    title: str | None = None,
    category: object = None,
    keep_meta_from: DraftContent | None = None,
) -> None:
    content = result.content
    content.parse_notes = result.notes
    if keep_meta_from is not None:
        # Re-parse keeps what the user already typed for the exam meta and attempt.
        if keep_meta_from.exam.title.strip():
            content.exam.title = keep_meta_from.exam.title
        content.exam.category = keep_meta_from.exam.category or content.exam.category
        content.exam.description = keep_meta_from.exam.description
        content.attempt = keep_meta_from.attempt
    if title:
        content.exam.title = title
    if category is not None:
        content.exam.category = category  # type: ignore[assignment]
    derive_answer_sources(content, ImportMethod(draft.method))
    draft.adapter = result.adapter
    draft.content = content.model_dump(mode="json")
    draft.error_code = None
    draft.error_message = None


def _content(draft: ImportDraft) -> DraftContent:
    return DraftContent.model_validate(draft.content)


def _revalidate(db: Session, draft: ImportDraft) -> list[Issue]:
    content = _content(draft)
    issues = list(content.parse_notes) + structural_issues(content)
    if draft.status != ImportStatus.COMMITTED:
        issues += duplicate_issues(db, draft, content)
    draft.issues = [i.model_dump(mode="json") for i in issues]
    if draft.status not in {ImportStatus.COMMITTED, ImportStatus.FAILED}:
        has_errors = any(i.severity == "error" for i in issues)
        draft.status = (ImportStatus.NEEDS_REVIEW if has_errors else ImportStatus.READY).value
    return issues


def _load(db: Session, draft_id: uuid.UUID, *, for_update: bool = False) -> ImportDraft:
    stmt = select(ImportDraft).where(ImportDraft.id == draft_id)
    if for_update:
        stmt = stmt.with_for_update()
    draft = db.scalar(stmt)
    if draft is None:
        raise NotFoundError("Không tìm thấy bản nháp nhập đề.", details={"draft_id": str(draft_id)})
    return draft


def _attempt_id(db: Session, draft_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(ExamAttempt.id).where(ExamAttempt.import_draft_id == draft_id))


def to_read(db: Session, draft: ImportDraft) -> DraftRead:
    content = _content(draft)
    issues = [Issue.model_validate(i) for i in draft.issues]
    return DraftRead(
        id=draft.id,
        status=ImportStatus(draft.status),
        method=ImportMethod(draft.method),
        adapter=draft.adapter,
        source_url=draft.source_url,
        raw_input=draft.raw_input,
        content=content,
        issues=issues,
        summary=summarize(content, issues),
        assets=[AssetRead.model_validate(a) for a in draft.assets],
        error_code=draft.error_code,
        error_message=draft.error_message,
        version=draft.version,
        exam_id=draft.exam_id,
        attempt_id=_attempt_id(db, draft.id),
        committed_at=draft.committed_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


# ------------------------------------------------------------------ create
def _create_from_raw(
    db: Session,
    settings: Settings,
    method: ImportMethod,
    raw: str,
    data: TextImportCreate | HtmlImportCreate,
) -> DraftRead:
    _check_text_size(settings, method, raw)
    source_url = data.source_url
    if method == ImportMethod.HTML and source_url is None:
        source_url = canonical_url(raw)
    draft = ImportDraft(
        status=ImportStatus.PARSING.value,
        method=method.value,
        source_url=source_url,
        raw_input=raw,
        raw_sha256=_sha(raw),
        content=DraftContent().model_dump(mode="json"),
        issues=[],
    )
    db.add(draft)
    db.flush()
    try:
        result = _run_adapter(method, raw, source_url)
    except UnsupportedInputError as exc:
        draft.status = ImportStatus.FAILED.value
        draft.error_code, draft.error_message = exc.code, exc.message
    else:
        _apply_result(draft, result, title=data.title, category=data.category)
        draft.status = ImportStatus.UPLOADED.value
        _revalidate(db, draft)
    db.commit()
    db.refresh(draft)
    return to_read(db, draft)


def create_from_text(db: Session, settings: Settings, data: TextImportCreate) -> DraftRead:
    return _create_from_raw(db, settings, ImportMethod.TEXT, data.text, data)


def create_from_html(db: Session, settings: Settings, data: HtmlImportCreate) -> DraftRead:
    return _create_from_raw(db, settings, ImportMethod.HTML, data.html, data)


def create_from_browser_capture(
    db: Session, settings: Settings, data: BrowserCapture
) -> tuple[DraftRead, bool]:
    """Turn a validated extension capture into the same editable PR2 import draft."""
    raw = json.dumps(
        data.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    _check_text_size(settings, ImportMethod.HTML, raw)
    digest = _sha(raw)
    existing = db.scalar(
        select(ImportDraft).where(
            ImportDraft.method == ImportMethod.BROWSER_CAPTURE.value,
            ImportDraft.raw_sha256 == digest,
        )
    )
    if existing is not None:
        return to_read(db, existing), False

    passage_by_text: dict[str, str] = {}
    passages: list[DraftPassage] = []
    questions: list[DraftQuestion] = []
    qtypes: list[QuestionType] = []
    for index, item in enumerate(data.questions, start=1):
        passage_key: str | None = None
        if item.passage:
            passage_key = passage_by_text.get(item.passage)
            if passage_key is None:
                passage_key = f"p{len(passages) + 1}"
                passage_by_text[item.passage] = passage_key
                passages.append(DraftPassage(key=passage_key, content=item.passage))

        qtype = guess_question_type(item.section_heading) or QuestionType.OTHER
        qtypes.append(qtype)
        notes: list[ParserNote] = []
        if item.source_correct_answer_index is None:
            notes.append(
                ParserNote(
                    code="missing_source_answer",
                    message=(
                        "Không đọc được đáp án chuẩn từ trang; hãy kiểm tra hoặc nhập thủ công."
                    ),
                )
            )
        if data.capture_state == "graded" and item.answer_source != "page_result":
            notes.append(
                ParserNote(
                    code="graded_result_unconfirmed",
                    message=(
                        "Trang không cung cấp dấu chấm điểm cho câu này; "
                        "hãy kiểm tra lựa chọn và đáp án."
                    ),
                )
            )
        if item.source_key_conflict:
            notes.append(
                ParserNote(
                    code="source_key_conflict",
                    message="Đáp án trên dấu chấm điểm khác đáp án trong key trang; cần xác minh.",
                )
            )
        is_example = item.points == 0 or item.question_text.lstrip().startswith(("（例）", "(例)"))
        questions.append(
            DraftQuestion(
                key=f"capture-{index}",
                include=not is_example,
                question_number=item.number,
                question_type=qtype,
                question_text=item.question_text,
                options=item.options,
                passage_key=passage_key,
                site_answer=(item.source_correct_answer_index + 1)
                if item.source_correct_answer_index is not None
                else None,
                user_answer=(item.selected_answer_index + 1)
                if item.selected_answer_index is not None
                else None,
                correct_answer=(item.source_correct_answer_index + 1)
                if item.source_correct_answer_index is not None
                else None,
                answer_confirmed=False,
                parser_notes=notes,
                reviewed=False,
                points=item.points,
                is_example=is_example,
            )
        )
    category = data.category or category_for_types(qtypes)
    has_attempt = data.capture_state == "graded" and any(
        q.user_answer is not None for q in questions
    )
    content = DraftContent(
        exam=DraftExam(title=data.exam_title, category=category),
        passages=passages,
        questions=questions,
        attempt=DraftAttempt(
            create=has_attempt,
            # Capture time is known; start time remains blank for the learner to enter.
            completed_at=data.captured_at if has_attempt else None,
        ),
    )
    draft = ImportDraft(
        status=ImportStatus.UPLOADED.value,
        method=ImportMethod.BROWSER_CAPTURE.value,
        adapter="dethitiengnhat_capture",
        source_url=data.source_url,
        raw_input=raw,
        raw_sha256=digest,
        content=content.model_dump(mode="json"),
        issues=[],
    )
    db.add(draft)
    try:
        db.flush()
        _revalidate(db, draft)
        db.commit()
    except IntegrityError:
        db.rollback()
        retry = db.scalar(
            select(ImportDraft).where(
                ImportDraft.method == ImportMethod.BROWSER_CAPTURE.value,
                ImportDraft.raw_sha256 == digest,
            )
        )
        if retry is not None:
            return to_read(db, retry), False
        raise
    db.refresh(draft)
    return to_read(db, draft), True


def create_from_images(
    db: Session,
    settings: Settings,
    files: list[UploadedFile],
    *,
    source_url: str | None,
    title: str | None,
    category: object,
) -> DraftRead:
    engine = get_engine(settings)
    availability = engine.availability()
    if not availability.available:
        raise OcrUnavailableError(
            availability.reason or "OCR không khả dụng.",
            details={"fallback": "Dùng tab “Dán văn bản”."},
        )
    if not files:
        raise DomainValidationError("Chưa chọn ảnh nào.")
    if len(files) > settings.import_max_images:
        raise DomainValidationError(
            f"Tối đa {settings.import_max_images} ảnh mỗi lần.",
            details={"limit": settings.import_max_images},
        )
    for f in files:
        if len(f.data) > settings.import_max_image_bytes:
            raise PayloadTooLargeError(
                f"Ảnh “{f.filename}” vượt quá "
                f"{settings.import_max_image_bytes // (1024 * 1024)} MB.",
                details={"file": f.filename, "limit": settings.import_max_image_bytes},
            )
        if not f.data:
            raise DomainValidationError(f"Ảnh “{f.filename}” rỗng.", details={"file": f.filename})
    # Validate & normalise every file before storing anything.
    normalised = [
        (
            f,
            images.normalise(
                f.data, filename=f.filename, max_pixels=settings.import_max_image_pixels
            ),
        )
        for f in files
    ]

    draft = ImportDraft(
        status=ImportStatus.UPLOADED.value,
        method=ImportMethod.IMAGES.value,
        source_url=source_url,
        raw_input=None,
        raw_sha256=_sha("|".join(n.sha256 for _, n in normalised)),
        content=DraftContent().model_dump(mode="json"),
        issues=[],
    )
    db.add(draft)
    db.flush()
    written: list[Path] = []
    try:
        for position, (f, img) in enumerate(normalised):
            asset_id = uuid.uuid4()
            rel = storage.relative_path(draft.id, asset_id)
            written.append(storage.write_bytes(settings, rel, img.png_bytes))
            draft.assets.append(
                ImportAsset(
                    id=asset_id,
                    position=position,
                    storage_path=rel,
                    original_filename=Path(f.filename).name[:255] or None,
                    detected_type=img.detected_type,
                    stored_type="image/png",
                    byte_size=len(img.png_bytes),
                    width=img.width,
                    height=img.height,
                    sha256=img.sha256,
                    ocr_status=OcrStatus.PENDING.value,
                )
            )
        draft.status = ImportStatus.PARSING.value
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    _ocr_and_parse(db, settings, draft, title=title, category=category)
    db.refresh(draft)
    return to_read(db, draft)


def _ocr_and_parse(
    db: Session,
    settings: Settings,
    draft: ImportDraft,
    *,
    title: str | None = None,
    category: object = None,
    keep_meta_from: DraftContent | None = None,
) -> None:
    engine = get_engine(settings)
    for asset in draft.assets:
        if asset.ocr_status == OcrStatus.DONE:
            continue
        try:
            asset.ocr_text = engine.recognise(storage.resolve(settings, asset.storage_path))
            asset.ocr_status = OcrStatus.DONE.value
            asset.ocr_engine = engine.name
        except OcrError as exc:
            logger.warning("OCR failed for asset %s: %s", asset.id, exc)
            asset.ocr_status = OcrStatus.FAILED.value
            asset.ocr_text = None
    texts = [a.ocr_text for a in draft.assets if a.ocr_status == OcrStatus.DONE and a.ocr_text]
    if not texts:
        draft.status = ImportStatus.FAILED.value
        draft.error_code = "ocr_failed"
        draft.error_message = (
            "OCR không đọc được ảnh nào. Hãy thử ảnh rõ hơn hoặc dùng “Dán văn bản”."
        )
        db.commit()
        return
    result = _run_adapter(ImportMethod.IMAGES, "\n".join(texts), draft.source_url)
    failed = [a.position + 1 for a in draft.assets if a.ocr_status == OcrStatus.FAILED]
    if failed:
        result.notes.insert(
            0,
            Issue(
                severity="warning",
                code="ocr_partial",
                message=f"OCR lỗi ở ảnh số {', '.join(map(str, failed))}.",
            ),
        )
    _apply_result(draft, result, title=title, category=category, keep_meta_from=keep_meta_from)
    draft.status = ImportStatus.UPLOADED.value
    _revalidate(db, draft)
    db.commit()


# ------------------------------------------------------------------ read
def get_draft(db: Session, draft_id: uuid.UUID) -> DraftRead:
    return to_read(db, _load(db, draft_id))


def list_drafts(
    db: Session, page: PageParams, status_filter: ImportStatus | None = None
) -> tuple[list[DraftListItem], int]:
    conds = [ImportDraft.status == status_filter.value] if status_filter else []
    total = db.scalar(select(func.count()).select_from(ImportDraft).where(*conds)) or 0
    drafts = db.scalars(
        select(ImportDraft)
        .where(*conds)
        .order_by(ImportDraft.created_at.desc(), ImportDraft.id)
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    items = []
    for d in drafts:
        content = d.content or {}
        items.append(
            DraftListItem(
                id=d.id,
                status=ImportStatus(d.status),
                method=ImportMethod(d.method),
                adapter=d.adapter,
                source_url=d.source_url,
                title=str((content.get("exam") or {}).get("title") or ""),
                question_count=len(content.get("questions") or []),
                issues=[Issue.model_validate(issue) for issue in (d.issues or [])],
                error_code=d.error_code,
                error_message=d.error_message,
                exam_id=d.exam_id,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )
    return items, total


def asset_path(db: Session, settings: Settings, draft_id: uuid.UUID, asset_id: uuid.UUID) -> Path:
    asset = db.scalar(
        select(ImportAsset).where(ImportAsset.id == asset_id, ImportAsset.draft_id == draft_id)
    )
    if asset is None:
        raise NotFoundError("Không tìm thấy ảnh.")
    path = storage.resolve(settings, asset.storage_path)
    if not path.is_file():
        raise NotFoundError("Tệp ảnh không còn trên máy chủ.")
    return path


# ------------------------------------------------------------------ edit
def _ensure_editable(draft: ImportDraft) -> None:
    if draft.status == ImportStatus.COMMITTED:
        raise ConflictError(
            "Bản nháp đã được lưu thành đề, không thể sửa.",
            details={"exam_id": str(draft.exam_id) if draft.exam_id else None},
        )


def update_draft(db: Session, draft_id: uuid.UUID, data: DraftUpdate) -> DraftRead:
    draft = _load(db, draft_id, for_update=True)
    _ensure_editable(draft)
    if data.version != draft.version:
        raise ConflictError(
            "Bản nháp đã được thay đổi ở nơi khác. Hãy tải lại trước khi lưu.",
            details={"code": "version_conflict", "current_version": draft.version},
        )
    if "source_url" in data.model_fields_set:
        draft.source_url = data.source_url
    if data.content is not None:
        stored = _content(draft)
        new = data.content
        new.parse_notes = stored.parse_notes  # read-only for clients
        before = {q.key: q for q in stored.questions}
        for q in new.questions:
            old = before.get(q.key)
            # Changing an already confirmed key requires confirming again.
            if (
                old is not None
                and old.answer_confirmed
                and q.answer_confirmed
                and old.correct_answer != q.correct_answer
            ):
                q.answer_confirmed = False
        derive_answer_sources(new, ImportMethod(draft.method))
        draft.content = new.model_dump(mode="json")
    if data.asset_order is not None:
        current = {a.id: a for a in draft.assets}
        if sorted(map(str, data.asset_order)) != sorted(map(str, current)):
            raise DomainValidationError("asset_order phải chứa đúng tất cả ảnh của bản nháp.")
        for position, asset_id in enumerate(data.asset_order):
            current[asset_id].position = position
    if draft.status == ImportStatus.FAILED and data.content is not None:
        draft.status = ImportStatus.UPLOADED.value
    draft.version += 1
    _revalidate(db, draft)
    db.commit()
    db.refresh(draft)
    return to_read(db, draft)


def reparse(
    db: Session, settings: Settings, draft_id: uuid.UUID, data: ReparseRequest
) -> DraftRead:
    draft = _load(db, draft_id, for_update=True)
    _ensure_editable(draft)
    method = ImportMethod(draft.method)
    keep = _content(draft)
    if method == ImportMethod.BROWSER_CAPTURE:
        raise DomainValidationError(
            "Capture có cấu trúc không thể phân tích lại từ HTML. "
            "Hãy sửa trực tiếp trong bản xem trước."
        )
    if method == ImportMethod.IMAGES:
        if data.raw_input is not None:
            raise DomainValidationError("Bản nháp từ ảnh không có văn bản gốc để thay thế.")
        if not get_engine(settings).availability().available and any(
            a.ocr_status != OcrStatus.DONE for a in draft.assets
        ):
            raise OcrUnavailableError("OCR không khả dụng để đọc lại ảnh.")
        draft.status = ImportStatus.PARSING.value
        draft.version += 1
        db.commit()
        _ocr_and_parse(db, settings, draft, keep_meta_from=keep)
        db.refresh(draft)
        return to_read(db, draft)

    raw = data.raw_input if data.raw_input is not None else (draft.raw_input or "")
    _check_text_size(settings, method, raw)
    draft.raw_input = raw
    draft.raw_sha256 = _sha(raw)
    try:
        result = _run_adapter(method, raw, draft.source_url)
    except UnsupportedInputError as exc:
        draft.status = ImportStatus.FAILED.value
        draft.error_code, draft.error_message = exc.code, exc.message
    else:
        _apply_result(draft, result, keep_meta_from=keep)
        draft.status = ImportStatus.UPLOADED.value
        _revalidate(db, draft)
    draft.version += 1
    db.commit()
    db.refresh(draft)
    return to_read(db, draft)


def validate(db: Session, draft_id: uuid.UUID) -> DraftRead:
    draft = _load(db, draft_id, for_update=True)
    _ensure_editable(draft)
    _revalidate(db, draft)
    db.commit()
    db.refresh(draft)
    return to_read(db, draft)


def delete_draft(db: Session, settings: Settings, draft_id: uuid.UUID) -> None:
    draft = _load(db, draft_id, for_update=True)
    db.delete(draft)  # attempts keep their history (import_draft_id → NULL)
    db.commit()
    storage.delete_draft_dir(settings, draft_id)


# ------------------------------------------------------------------ commit
def _answer_fields(q: DraftQuestion) -> tuple[int | None, str, str | None]:
    if q.correct_answer is None:
        return None, AnswerStatus.MISSING.value, None
    trust = AnswerStatus.VERIFIED if q.answer_confirmed else AnswerStatus.UNVERIFIED
    source = q.answer_source.value if q.answer_source else AnswerSource.USER_ENTERED.value
    return q.correct_answer, trust.value, source


def commit(db: Session, draft_id: uuid.UUID, req: CommitRequest) -> CommitResult:
    draft = _load(db, draft_id, for_update=True)  # serialises double clicks
    if draft.status == ImportStatus.COMMITTED:
        assert draft.exam_id is not None
        return CommitResult(
            draft_id=draft.id,
            exam_id=draft.exam_id,
            attempt_id=_attempt_id(db, draft.id),
            already_committed=True,
            created_questions=0,
            reused_questions=0,
            upgraded_answers=0,
            warnings=[],
        )
    if draft.status in {ImportStatus.FAILED, ImportStatus.PARSING}:
        raise DomainValidationError("Bản nháp chưa được phân tích thành công.")

    content = _content(draft)
    issues = _revalidate(db, draft)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        db.commit()  # persist the refreshed issues/status
        raise DomainValidationError(
            "Bản nháp còn lỗi cần sửa trước khi lưu.",
            details=[i.model_dump(mode="json") for i in errors],
        )

    included = [q for q in content.questions if q.include]
    warnings: list[Issue] = []
    created = reused = upgraded = 0

    if req.target == "new":
        if draft.source_url:
            existing = db.scalar(select(Exam.id).where(Exam.source_url == draft.source_url))
            if existing:
                raise ConflictError(
                    "Đã có đề với URL nguồn này. Chọn “Dùng đề đã có” để thêm vào đề đó.",
                    details={"code": "duplicate_exam", "existing_exam_id": str(existing)},
                )
        assert content.exam.category is not None
        exam = Exam(
            title=content.exam.title.strip(),
            level=content.exam.level.value,
            category=content.exam.category.value,
            description=content.exam.description or None,
            source_url=draft.source_url,
            status=ExamStatus.READY.value,
        )
        db.add(exam)
        db.flush()
        existing_questions: list[Question] = []
    else:
        assert req.existing_exam_id is not None
        exam_or_none = db.scalar(
            select(Exam).where(Exam.id == req.existing_exam_id).with_for_update(of=Exam)
        )
        if exam_or_none is None:
            raise NotFoundError("Không tìm thấy đề để dùng lại.")
        exam = exam_or_none
        existing_questions = list(db.scalars(select(Question).where(Question.exam_id == exam.id)))

    # Passages: reuse an identical passage of the target exam, else create (in draft order).
    passage_ids: dict[str, uuid.UUID] = {}
    existing_passages = {
        p.content: p.id for p in db.scalars(select(Passage).where(Passage.exam_id == exam.id))
    }
    used_keys = {q.passage_key for q in included if q.passage_key}
    for p in content.passages:
        if p.key not in used_keys:
            continue
        if p.content in existing_passages:
            passage_ids[p.key] = existing_passages[p.content]
        else:
            passage = Passage(exam_id=exam.id, content=p.content)
            db.add(passage)
            db.flush()
            passage_ids[p.key] = passage.id

    by_exact = {(q.question_text, tuple(q.options)): q for q in existing_questions}
    numbers = {q.question_number: q for q in existing_questions}
    hashes = {q.content_hash: q for q in existing_questions}
    question_for_key: dict[str, Question] = {}
    conflicts: list[dict[str, object]] = []

    for dq in included:
        assert dq.question_number is not None
        passage_id = passage_ids.get(dq.passage_key) if dq.passage_key else None
        key, trust, source = _answer_fields(dq)
        match = by_exact.get((dq.question_text, tuple(dq.options)))
        if match is not None:
            reused += 1
            question_for_key[dq.key] = match
            if (
                key is not None
                and match.answer_status != AnswerStatus.VERIFIED
                and (trust == AnswerStatus.VERIFIED or match.correct_answer is None)
            ):
                match.correct_answer, match.answer_status, match.answer_source = key, trust, source
                upgraded += 1
            elif key is not None and match.correct_answer not in (None, key):
                warnings.append(
                    Issue(
                        severity="warning",
                        code="answer_conflict",
                        message=(
                            f"Câu {match.question_number}: đáp án trong đề đã có "
                            f"({match.correct_answer}) khác bản nhập ({key}); giữ nguyên đề đã có."
                        ),
                        question_key=dq.key,
                    )
                )
            continue
        content_hash = question_content_hash(passage_id, dq.question_text, dq.options)
        if dq.question_number in numbers or content_hash in hashes:
            conflicts.append(
                {
                    "question_key": dq.key,
                    "question_number": dq.question_number,
                    "reason": "number_taken"
                    if dq.question_number in numbers
                    else "similar_content",
                }
            )
            continue
        question = Question(
            exam_id=exam.id,
            passage_id=passage_id,
            question_number=dq.question_number,
            question_type=dq.question_type.value,
            question_text=dq.question_text,
            options=list(dq.options),
            correct_answer=key,
            answer_status=trust,
            answer_source=source,
            content_hash=content_hash,
            fingerprint=question_fingerprint(dq.question_text, list(dq.options)),
        )
        db.add(question)
        numbers[dq.question_number] = question
        hashes[content_hash] = question
        question_for_key[dq.key] = question
        created += 1

    if conflicts:
        db.rollback()
        raise ConflictError(
            "Một số câu xung đột với câu đã có trong đề (trùng số câu hoặc gần giống nội dung).",
            details={"code": "question_conflict", "conflicts": conflicts},
        )
    db.flush()

    attempt_id: uuid.UUID | None = None
    if content.attempt.create:
        assert content.attempt.started_at and content.attempt.completed_at
        if exam.status == ExamStatus.ARCHIVED:
            raise DomainValidationError("Không thể thêm bài làm vào đề đã lưu trữ.")
        check_attempt_times(content.attempt.started_at, content.attempt.completed_at)
        all_questions = list(
            db.scalars(
                select(Question)
                .where(Question.exam_id == exam.id)
                .order_by(Question.question_number)
            )
        )
        selections: dict[uuid.UUID, int | None] = {
            question_for_key[q.key].id: q.user_answer
            for q in included
            if q.user_answer is not None and q.key in question_for_key
        }
        for q in included:
            target = question_for_key.get(q.key)
            if (
                target is not None
                and q.user_answer is not None
                and q.user_answer > len(target.options)
            ):
                raise DomainValidationError(f"Lựa chọn của câu {q.question_number} không hợp lệ.")
        attempt = build_graded_attempt(
            exam=exam,
            questions=all_questions,
            selections=selections,
            started_at=content.attempt.started_at,
            completed_at=content.attempt.completed_at,
            source=AttemptSource.IMPORT,
            import_draft_id=draft.id,
        )
        db.add(attempt)
        db.flush()
        attempt_id = attempt.id

    draft.status = ImportStatus.COMMITTED.value
    draft.exam_id = exam.id
    draft.committed_at = utcnow()
    draft.version += 1
    db.commit()
    return CommitResult(
        draft_id=draft.id,
        exam_id=exam.id,
        attempt_id=attempt_id,
        already_committed=False,
        created_questions=created,
        reused_questions=reused,
        upgraded_answers=upgraded,
        warnings=warnings,
    )
