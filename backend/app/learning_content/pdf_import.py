"""Project the operator-authorized PDF into the existing transactional content importer."""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.learning_content.mimikara_pdf import PACK_ID, PDF_FILENAME, SOURCE_ID, extract_words
from app.learning_content.models import LearningContentPack
from app.learning_content.source import (
    SourceLesson,
    SourcePack,
    SourceRecord,
    SourceSnapshot,
    SourceValidationError,
    canonical_hash,
)
from app.learning_content.study_models import LearningSourceRight


def pdf_inventory(settings: Settings) -> dict[str, object] | None:
    path = settings.mimikara_pdf_path
    if not path.is_file():
        return None
    digest, rows = extract_words(path)
    return {
        "pack_id": PACK_ID,
        "source_id": SOURCE_ID,
        "source_name": "Mimikara N3 — PDF VTI Mirai/Minato (bản dùng cá nhân)",
        "source_license": (
            "Chỉ nhập khi người vận hành xác nhận quyền dùng cá nhân; không cấp quyền tái phân phối"
        ),
        "license_verified": False,
        "source_content_hash": digest,
        "row_count": len(rows),
        "file_name": PDF_FILENAME,
    }


def pdf_snapshot(db: Session, settings: Settings) -> SourceSnapshot:
    digest, rows = extract_words(settings.mimikara_pdf_path)
    right = db.get(LearningSourceRight, (PACK_ID, SOURCE_ID))
    if (
        right is None
        or not right.approved
        or right.scope != "private"
        or right.source_content_hash != digest
    ):
        raise SourceValidationError(
            "PDF chưa có khai báo quyền dùng cá nhân cho đúng SHA-256 của tệp hiện tại"
        )
    previous = db.get(LearningContentPack, PACK_ID)
    version = 1 if previous is None else previous.source_version + (previous.source_hash != digest)
    grouped: dict[int, list[SourceRecord]] = defaultdict(list)
    for row in rows:
        payload = {
            "expression": row.expression,
            "reading": row.reading,
            "meaningVi": row.meaning_vi,
            "sourceRow": row.number,
            "sourcePage": row.page,
            "sourceLessonNumber": row.lesson_number,
        }
        grouped[row.lesson_number].append(
            SourceRecord(
                source_ref=str(row.number),
                entity_type="vocabulary",
                order_index=len(grouped[row.lesson_number]),
                source_id=SOURCE_ID,
                source_name=right.source_name,
                source_license=right.allowed_usage,
                payload=payload,
                content_hash=canonical_hash(payload),
                example_refs=(),
                pack_id=PACK_ID,
            )
        )
    lessons = tuple(
        SourceLesson(
            source_id=f"pdf-lesson-{number:02d}",
            number=number,
            order_index=number - 1,
            title=f"Mimikara — Bài {number:02d}",
            description="Thứ tự gốc trong PDF; ví dụ không có trong nguồn này.",
            content_items=tuple(grouped[number]),
            pack_id=PACK_ID,
        )
        for number in range(1, 13)
    )
    pack = SourcePack(
        pack_id=PACK_ID,
        title="Mimikara N3 — PDF cá nhân",
        jlpt_level="N3",
        version=version,
        relative_path=f"pdf:{PDF_FILENAME}",
        source_hash=digest,
        source_commit_sha=f"pdf:{digest}",
        source_manifest_hash=digest,
        blocked_count=0,
        lessons=lessons,
        examples=(),
    )
    return SourceSnapshot(f"pdf:{digest}", digest, (pack,))
