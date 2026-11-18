"""Single-user personal word vault; extension receives only a save-scoped credential."""

import hashlib
import json
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Text, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.responses import DataResponse
from app.core.security import get_principal
from app.database.enums import ReviewRating, SrsState
from app.database.session import get_db
from app.learning_content.my_words_models import (
    MyWord,
    MyWordExtensionCredential,
    MyWordProgress,
    MyWordReviewEvent,
)
from app.reviews.srs import DEFAULT_LADDER, NEW_ITEM, Ladder, SrsSnapshot, resolve_zone, schedule
from app.sync.admin import require_https_for_remote_sync, require_sync_admin

router = APIRouter(prefix="/my-words", tags=["my-words"])
web = APIRouter(dependencies=[Depends(get_principal)])
DB = Annotated[Session, Depends(get_db)]


class WordFields(BaseModel):
    original_text: str = Field(min_length=1, max_length=200)
    language: Literal["ja", "en", "vi"]
    meanings: dict[Literal["ja", "en", "vi"], list[str]] = Field(default_factory=dict)
    japanese_reading: str | None = Field(default=None, max_length=300)
    english_ipa: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=2048)
    source_title: str | None = Field(default=None, max_length=300)
    context: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("meanings")
    @classmethod
    def meanings_valid(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(
            len(entries) > 20 or any(not entry.strip() or len(entry) > 500 for entry in entries)
            for entries in value.values()
        ):
            raise ValueError("Mỗi nghĩa phải có nội dung và tối đa 500 ký tự")
        return value

    @field_validator("source_url")
    @classmethod
    def source_url_valid(cls, value: str | None) -> str | None:
        if value and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError("Nguồn phải là URL HTTP/HTTPS")
        return value


class WordInput(WordFields):
    request_id: uuid.UUID


class WordEdit(WordFields):
    pass


class RatingInput(BaseModel):
    request_id: uuid.UUID
    rating: ReviewRating
    time_zone: str = Field(default="Asia/Bangkok", max_length=100)


class CredentialInput(BaseModel):
    label: str = Field(min_length=1, max_length=100)


def _fingerprint(
    language: str,
    text: str,
    meanings: dict[Literal["ja", "en", "vi"], list[str]],
) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().casefold()
    glosses = {
        key: [unicodedata.normalize("NFKC", item).strip().casefold() for item in entries]
        for key, entries in sorted(meanings.items())
    }
    return hashlib.sha256(
        json.dumps([language, normalized, glosses], ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _word_data(db: Session, word: MyWord) -> dict[str, Any]:
    progress = db.get(MyWordProgress, word.id)
    return {
        "id": str(word.id),
        "original_text": word.original_text,
        "language": word.language,
        "meanings": word.meanings,
        "japanese_reading": word.japanese_reading,
        "english_ipa": word.english_ipa,
        "source_url": word.source_url,
        "source_title": word.source_title,
        "context": word.context,
        "tags": word.tags,
        "created_at": word.created_at,
        "updated_at": word.updated_at,
        "progress": None
        if progress is None
        else {
            "state": progress.state,
            "due_at": progress.due_at,
            "review_count": progress.review_count,
        },
    }


def _save_word(db: Session, payload: WordInput) -> tuple[MyWord, bool]:
    existing_request = db.scalar(select(MyWord).where(MyWord.request_id == payload.request_id))
    fingerprint = _fingerprint(payload.language, payload.original_text, payload.meanings)
    if existing_request:
        if existing_request.fingerprint != fingerprint:
            raise HTTPException(409, "request_id đã dùng cho từ khác")
        return existing_request, False
    existing = db.scalar(select(MyWord).where(MyWord.fingerprint == fingerprint))
    if existing:
        if existing.archived_at:
            existing.archived_at = None
        if payload.source_url and not existing.source_url:
            existing.source_url = payload.source_url
            existing.source_title = payload.source_title
        db.commit()
        return existing, False
    inserted_id = db.scalar(
        pg_insert(MyWord)
        .values(
            id=uuid.uuid4(),
            request_id=payload.request_id,
            fingerprint=fingerprint,
            original_text=payload.original_text.strip(),
            language=payload.language,
            meanings=payload.meanings,
            japanese_reading=payload.japanese_reading,
            english_ipa=payload.english_ipa,
            source_url=payload.source_url,
            source_title=payload.source_title,
            context=payload.context,
            tags=payload.tags,
        )
        .on_conflict_do_nothing()
        .returning(MyWord.id)
    )
    word = db.scalar(select(MyWord).where(MyWord.request_id == payload.request_id))
    if word and word.fingerprint != fingerprint:
        db.rollback()
        raise HTTPException(409, "request_id đã dùng cho từ khác")
    if word is None:
        word = db.scalar(select(MyWord).where(MyWord.fingerprint == fingerprint))
    assert word is not None
    created = inserted_id is not None
    if not created and payload.source_url and not word.source_url:
        word.source_url = payload.source_url
        word.source_title = payload.source_title
    db.commit()
    return word, created


@web.get("/")
def list_words(
    db: DB,
    q: Annotated[str | None, Query(max_length=100)] = None,
    language: Literal["ja", "en", "vi"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> DataResponse[dict[str, Any]]:
    stmt = select(MyWord).where(MyWord.archived_at.is_(None))
    if language:
        stmt = stmt.where(MyWord.language == language)
    if q:
        stmt = stmt.where(
            or_(MyWord.original_text.ilike(f"%{q}%"), MyWord.meanings.cast(Text).ilike(f"%{q}%"))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    words = db.scalars(
        stmt.order_by(MyWord.created_at.desc(), MyWord.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return DataResponse(
        data={"items": [_word_data(db, word) for word in words], "total": total, "page": page}
    )


@web.post("/", status_code=201)
def create_word(payload: WordInput, db: DB) -> DataResponse[dict[str, Any]]:
    word, created = _save_word(db, payload)
    return DataResponse(data={"word": _word_data(db, word), "created": created})


@web.put("/{word_id}")
def edit_word(word_id: uuid.UUID, payload: WordEdit, db: DB) -> DataResponse[dict[str, Any]]:
    word = db.get(MyWord, word_id)
    if word is None or word.archived_at:
        raise HTTPException(404, "Không tìm thấy từ")
    fingerprint = _fingerprint(payload.language, payload.original_text, payload.meanings)
    if db.scalar(select(MyWord.id).where(MyWord.fingerprint == fingerprint, MyWord.id != word_id)):
        raise HTTPException(409, "Từ với cùng dạng và nghĩa đã tồn tại")
    for key, value in payload.model_dump().items():
        setattr(word, key, value)
    word.fingerprint = fingerprint
    db.commit()
    return DataResponse(data=_word_data(db, word))


@web.delete("/{word_id}")
def archive_word(word_id: uuid.UUID, db: DB) -> DataResponse[dict[str, bool]]:
    word = db.get(MyWord, word_id)
    if word is None:
        raise HTTPException(404, "Không tìm thấy từ")
    word.archived_at = datetime.now(UTC)
    db.commit()
    return DataResponse(data={"archived": True})


@web.post("/{word_id}/review")
def review_word(word_id: uuid.UUID, payload: RatingInput, db: DB) -> DataResponse[dict[str, Any]]:
    word = db.scalar(
        select(MyWord).where(MyWord.id == word_id, MyWord.archived_at.is_(None)).with_for_update()
    )
    if word is None:
        raise HTTPException(404, "Không tìm thấy từ")
    prior = db.get(MyWordReviewEvent, payload.request_id)
    if prior:
        if prior.word_id != word_id or prior.rating != payload.rating.value:
            raise HTTPException(409, "request_id đã dùng cho đánh giá khác")
        return DataResponse(data={"word": _word_data(db, word), "duplicate": True})
    progress = db.get(MyWordProgress, word_id)
    current = (
        NEW_ITEM
        if progress is None
        else SrsSnapshot(
            SrsState(progress.state),
            progress.step_index,
            progress.interval_minutes,
            progress.due_at,
            progress.last_reviewed_at,
            progress.review_count,
            progress.lapse_count,
        )
    )
    now = datetime.now(UTC)
    next_state = schedule(
        current, payload.rating, now, resolve_zone(payload.time_zone), Ladder.parse(DEFAULT_LADDER)
    )
    assert next_state.due_at is not None
    if progress is None:
        progress = MyWordProgress(word_id=word_id)
        db.add(progress)
    progress.state = next_state.state.value
    progress.step_index = next_state.step_index or 0
    progress.interval_minutes = next_state.interval_minutes
    progress.due_at = next_state.due_at
    progress.last_reviewed_at = now
    progress.review_count = next_state.review_count
    progress.lapse_count = next_state.lapse_count
    db.add(
        MyWordReviewEvent(
            request_id=payload.request_id,
            word_id=word_id,
            rating=payload.rating.value,
            reviewed_at=now,
            due_at_after=next_state.due_at,
        )
    )
    db.commit()
    return DataResponse(data={"word": _word_data(db, word), "duplicate": False})


@web.post("/credentials", dependencies=[Depends(require_sync_admin)])
def issue_extension_credential(payload: CredentialInput, db: DB) -> DataResponse[dict[str, Any]]:
    token = secrets.token_urlsafe(48)
    row = MyWordExtensionCredential(
        label=payload.label, token_hash=hashlib.sha256(token.encode()).hexdigest()
    )
    db.add(row)
    db.commit()
    return DataResponse(data={"id": str(row.id), "token": token, "scope": "my-words:save"})


@web.get("/credentials", dependencies=[Depends(require_sync_admin)])
def list_extension_credentials(db: DB) -> DataResponse[list[dict[str, Any]]]:
    rows = db.scalars(
        select(MyWordExtensionCredential).order_by(MyWordExtensionCredential.created_at.desc())
    )
    return DataResponse(
        data=[
            {
                "id": str(row.id),
                "label": row.label,
                "created_at": row.created_at,
                "revoked_at": row.revoked_at,
            }
            for row in rows
        ]
    )


@web.post("/credentials/{credential_id}/revoke", dependencies=[Depends(require_sync_admin)])
def revoke_extension_credential(credential_id: uuid.UUID, db: DB) -> DataResponse[dict[str, bool]]:
    row = db.get(MyWordExtensionCredential, credential_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy credential")
    row.revoked_at = datetime.now(UTC)
    db.commit()
    return DataResponse(data={"revoked": True})


@router.post("/extension", dependencies=[Depends(require_https_for_remote_sync)], status_code=201)
def extension_save_word(
    payload: WordInput, db: DB, authorization: Annotated[str | None, Header()] = None
) -> DataResponse[dict[str, Any]]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Thiếu credential lưu từ")
    token = authorization.removeprefix("Bearer ")
    if len(token) < 40 or len(token) > 200:
        raise HTTPException(401, "Credential không hợp lệ")
    digest = hashlib.sha256(token.encode()).hexdigest()
    credential = db.scalar(
        select(MyWordExtensionCredential).where(
            MyWordExtensionCredential.token_hash == digest,
            MyWordExtensionCredential.revoked_at.is_(None),
        )
    )
    if credential is None:
        raise HTTPException(401, "Credential đã bị thu hồi hoặc không hợp lệ")
    word, created = _save_word(db, payload)
    return DataResponse(data={"id": str(word.id), "created": created})


router.include_router(web)
