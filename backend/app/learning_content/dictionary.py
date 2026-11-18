"""Exact, provenance-preserving local dictionary lookup; no generated translations."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import DataResponse
from app.core.security import get_principal
from app.database.session import get_db
from app.learning_content.models import LearningContentPack, LearningItem, LearningLesson

router = APIRouter(prefix="/dictionary", tags=["dictionary"], dependencies=[Depends(get_principal)])
DB = Annotated[Session, Depends(get_db)]


def detect_language(text: str) -> str | None:
    if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text):
        return "ja"
    if re.search(r"[À-ỹà-ỹ]", text):
        return "vi"
    if re.fullmatch(r"[A-Za-z][A-Za-z '\-]*", text):
        return "en"
    return None


@router.get("/lookup")
def lookup(
    q: Annotated[str, Query(min_length=1, max_length=200)], db: DB
) -> DataResponse[dict[str, Any]]:
    term = q.strip()
    language = detect_language(term)
    records = []
    if language == "ja":
        records = list(
            db.scalars(
                select(LearningItem)
                .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
                .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
                .where(
                    LearningItem.item_type == "vocabulary",
                    LearningItem.is_archived.is_(False),
                    LearningLesson.is_archived.is_(False),
                    LearningContentPack.is_archived.is_(False),
                    LearningItem.payload["expression"].astext == term,
                )
                .order_by(LearningItem.pack_id, LearningItem.source_ref)
                .limit(20)
            )
        )
    entries = [
        {
            "id": str(item.id),
            "expression": item.payload.get("expression"),
            "reading": item.payload.get("reading"),
            "meaning_vi": item.payload.get("meaningVi"),
            "source": item.source_name,
            "source_ref": item.source_ref,
        }
        for item in records
    ]
    return DataResponse(
        data={
            "query": term,
            "detected_language": language,
            "kind": "exact_dictionary" if entries else "unavailable",
            "entries": entries,
            "message": None
            if entries
            else "Chưa có mục từ được xác minh; hãy tự nhập nghĩa trước khi lưu.",
        }
    )
