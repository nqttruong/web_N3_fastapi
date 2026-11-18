"""Versioned QR bootstrap for a future Android client, verified with mock clients."""

import hashlib
import hmac
import ipaddress
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.responses import DataResponse
from app.database.session import get_db
from app.sync.admin import require_sync_admin
from app.sync.device import (
    SyncDevice,
    hash_token,
    pairing_attempt_for_address,
    record_failed_pairing_attempt,
)
from app.sync.qr_models import SyncQRAudit, SyncQRSession

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
TERMINAL = {"PAIRED", "EXPIRED", "REJECTED", "CANCELLED", "FAILED"}


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge: str = Field(min_length=24, max_length=100, pattern="^[A-Za-z0-9_-]+$")
    device_name: str = Field(min_length=1, max_length=120)
    device_credential: str = Field(min_length=48, max_length=200, pattern="^[A-Za-z0-9_-]+$")

    @field_validator("device_name")
    @classmethod
    def device_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Device name must not be blank")
        return value


class ConfirmInput(BaseModel):
    confirmation_code: str = Field(pattern="^[0-9]{6}$")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _transition(db: Session, session: SyncQRSession, state: str) -> None:
    session.status = state
    db.add(SyncQRAudit(session_id=session.id, state=state))


def _live(db: Session, session_id: uuid.UUID, *, lock: bool = False) -> SyncQRSession:
    query = select(SyncQRSession).where(SyncQRSession.id == session_id)
    session = db.scalar(query.with_for_update() if lock else query)
    if session is None:
        raise HTTPException(404, "Không tìm thấy phiên QR")
    if session.status not in TERMINAL and session.expires_at <= datetime.now(UTC):
        _transition(db, session, "EXPIRED")
        db.commit()
    return session


def _ticket(session_id: uuid.UUID, challenge: str, credential: str) -> str:
    return _hash(f"{session_id}|{challenge}|{credential}")


def _confirmation(ticket: str) -> str:
    return f"{int(_hash(ticket + '|confirm'), 16) % 1_000_000:06d}"


def _public_url(settings: Settings) -> str:
    value = (settings.sync_public_https_base_url or "").rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise HTTPException(503, "Cần cấu hình SYNC_PUBLIC_HTTPS_BASE_URL là HTTPS base URL hợp lệ")
    if parsed.hostname == "localhost":
        raise HTTPException(503, "QR không được dùng localhost; điện thoại cần HTTPS hostname thật")
    try:
        if ipaddress.ip_address(parsed.hostname).is_loopback:
            raise HTTPException(503, "QR không được dùng địa chỉ loopback")
    except ValueError:
        pass
    return value


def _admin_data(session: SyncQRSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "status": session.status,
        "device_name": session.device_name,
        "device_id": str(session.device_id) if session.device_id else None,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
    }


@router.post("/admin/qr-sessions", dependencies=[Depends(require_sync_admin)], status_code=201)
def create_qr_session(
    db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> DataResponse[dict[str, Any]]:
    base = _public_url(settings)
    now = datetime.now(UTC)
    # Serialize session rotation so the operator has only one live QR bootstrap at a time.
    db.execute(text("SELECT pg_advisory_xact_lock(71420261117)"))
    pending = db.scalars(
        select(SyncQRSession)
        .where(SyncQRSession.status.notin_(TERMINAL), SyncQRSession.expires_at > now)
        .with_for_update()
    )
    for old_session in pending:
        _transition(db, old_session, "CANCELLED")
    challenge = secrets.token_urlsafe(32)
    session = SyncQRSession(
        status="CREATED",
        challenge_hash=_hash(challenge),
        expires_at=now + timedelta(minutes=5),
        failure_count=0,
    )
    db.add(session)
    db.flush()
    _transition(db, session, "CREATED")
    _transition(db, session, "WAITING_FOR_DEVICE")
    db.commit()
    return DataResponse(
        data={
            **_admin_data(session),
            "qr_payload": {
                "version": 1,
                "base_url": base,
                "session_id": str(session.id),
                "challenge": challenge,
                "expires_at": session.expires_at,
            },
        }
    )


@router.get("/admin/qr-sessions/{session_id}", dependencies=[Depends(require_sync_admin)])
def admin_qr_status(session_id: uuid.UUID, db: DB) -> DataResponse[dict[str, Any]]:
    return DataResponse(data=_admin_data(_live(db, session_id)))


@router.post("/admin/qr-sessions/{session_id}/confirm", dependencies=[Depends(require_sync_admin)])
def confirm_qr_session(
    session_id: uuid.UUID, payload: ConfirmInput, db: DB
) -> DataResponse[dict[str, Any]]:
    session = _live(db, session_id, lock=True)
    if session.status == "PAIRED":
        return DataResponse(data=_admin_data(session))
    if session.status != "AWAITING_CONFIRMATION":
        raise HTTPException(409, f"Phiên QR không ở trạng thái chờ xác nhận: {session.status}")
    if not hmac.compare_digest(session.confirmation_hash or "", _hash(payload.confirmation_code)):
        session.failure_count += 1
        if session.failure_count >= 5:
            _transition(db, session, "FAILED")
        db.commit()
        raise HTTPException(401, "Mã xác nhận không khớp")
    if not session.credential_hash or not session.device_name:
        _transition(db, session, "FAILED")
        db.commit()
        raise HTTPException(409, "Thiếu credential thiết bị")
    device = SyncDevice(name=session.device_name, token_hash=session.credential_hash)
    db.add(device)
    db.flush()
    session.device_id = device.id
    _transition(db, session, "PAIRED")
    db.commit()
    return DataResponse(data=_admin_data(session))


@router.post("/admin/qr-sessions/{session_id}/cancel", dependencies=[Depends(require_sync_admin)])
def cancel_qr_session(session_id: uuid.UUID, db: DB) -> DataResponse[dict[str, Any]]:
    session = _live(db, session_id, lock=True)
    if session.status == "PAIRED":
        raise HTTPException(409, "Thiết bị đã ghép; dùng revoke")
    if session.status not in TERMINAL:
        _transition(db, session, "CANCELLED")
        db.commit()
    return DataResponse(data=_admin_data(session))


@router.post("/admin/qr-sessions/{session_id}/reject", dependencies=[Depends(require_sync_admin)])
def reject_qr_session(session_id: uuid.UUID, db: DB) -> DataResponse[dict[str, Any]]:
    session = _live(db, session_id, lock=True)
    if session.status not in {"CLAIMED", "AWAITING_CONFIRMATION"}:
        raise HTTPException(409, f"Không thể từ chối phiên ở trạng thái {session.status}")
    _transition(db, session, "REJECTED")
    db.commit()
    return DataResponse(data=_admin_data(session))


@router.post("/qr-sessions/{session_id}/claim")
def claim_qr_session(
    session_id: uuid.UUID, payload: ClaimInput, db: DB, request: Request
) -> DataResponse[dict[str, str]]:
    source_address = request.client.host if request.client else "unknown"
    attempt = pairing_attempt_for_address(db, source_address)
    session = _live(db, session_id, lock=True)
    if session.status not in {"WAITING_FOR_DEVICE", "CLAIMED", "AWAITING_CONFIRMATION"}:
        raise HTTPException(409, f"Phiên QR không nhận claim: {session.status}")
    if not hmac.compare_digest(session.challenge_hash, _hash(payload.challenge)):
        locked = record_failed_pairing_attempt(db, attempt)
        db.commit()
        if locked:
            raise HTTPException(
                429,
                "Ghép nối tạm khóa. Hãy thử lại sau 15 phút.",
                headers={"Retry-After": "900"},
            )
        raise HTTPException(401, "QR challenge không hợp lệ")
    credential_hash = hash_token(payload.device_credential)
    if db.scalar(select(SyncDevice.id).where(SyncDevice.token_hash == credential_hash)):
        raise HTTPException(409, "Credential thiết bị đã được sử dụng")
    ticket = _ticket(session_id, payload.challenge, payload.device_credential)
    if session.status in {"CLAIMED", "AWAITING_CONFIRMATION"}:
        if session.credential_hash != credential_hash:
            raise HTTPException(409, "Phiên QR đã được thiết bị khác nhận")
    else:
        attempt.failed_attempts = 0
        attempt.blocked_until = None
        session.credential_hash = credential_hash
        session.claim_ticket_hash = _hash(ticket)
        session.confirmation_hash = _hash(_confirmation(ticket))
        session.device_name = payload.device_name.strip()
        _transition(db, session, "CLAIMED")
        db.commit()
    return DataResponse(
        data={
            "status": session.status,
            "claim_ticket": ticket,
            "confirmation_code": _confirmation(ticket),
        }
    )


def _claimed(
    db: Session, session_id: uuid.UUID, ticket: str, *, lock: bool = False
) -> SyncQRSession:
    session = _live(db, session_id, lock=lock)
    if not session.claim_ticket_hash or not hmac.compare_digest(
        session.claim_ticket_hash, _hash(ticket)
    ):
        raise HTTPException(401, "Claim ticket không hợp lệ")
    return session


@router.post("/qr-sessions/{session_id}/ready")
def ready_qr_session(
    session_id: uuid.UUID,
    db: DB,
    claim_ticket: Annotated[str | None, Header(alias="X-Claim-Ticket")] = None,
) -> DataResponse[dict[str, Any]]:
    session = _claimed(db, session_id, claim_ticket or "", lock=True)
    if session.status == "CLAIMED":
        _transition(db, session, "AWAITING_CONFIRMATION")
        db.commit()
    elif session.status not in {"AWAITING_CONFIRMATION", "PAIRED"}:
        raise HTTPException(409, f"Phiên QR không sẵn sàng: {session.status}")
    return DataResponse(data=_admin_data(session))


@router.get("/qr-sessions/{session_id}")
def device_qr_status(
    session_id: uuid.UUID,
    db: DB,
    claim_ticket: Annotated[str | None, Header(alias="X-Claim-Ticket")] = None,
) -> DataResponse[dict[str, Any]]:
    session = _claimed(db, session_id, claim_ticket or "")
    return DataResponse(data=_admin_data(session))
