"""Device pairing and bearer authentication for Android sync."""

import hashlib
import math
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.database.session import get_db

PAIRING_CODE_TTL_MINUTES = 10
PAIRING_FAILURE_WINDOW = timedelta(minutes=15)
PAIRING_FAILURE_LIMIT = 5
PAIRING_LOCKOUT = timedelta(minutes=15)


class SyncDevice(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "sync_devices"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pull_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncPairingCode(Base):
    __tablename__ = "sync_pairing_codes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="sync_pairing_code_expiry"),
        Index("ix_sync_pairing_codes_expiry", "expires_at"),
    )


class SyncPairingAttempt(Base):
    __tablename__ = "sync_pairing_attempts"

    address_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="sync_pairing_attempts_nonnegative"),
    )


bearer = HTTPBearer(auto_error=False)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_pairing_code(
    db: Session, *, expires_in_minutes: int = PAIRING_CODE_TTL_MINUTES
) -> tuple[str, SyncPairingCode]:
    if not 1 <= expires_in_minutes <= 15:
        raise ValueError("Pairing code expiry must be between 1 and 15 minutes")
    now = datetime.now(UTC)
    # Serialize code rotation so simultaneous admin requests cannot leave two live codes.
    db.execute(text("SELECT pg_advisory_xact_lock(71420261116)"))
    db.execute(
        update(SyncPairingCode)
        .where(SyncPairingCode.used_at.is_(None), SyncPairingCode.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        delete(SyncPairingAttempt).where(
            SyncPairingAttempt.window_started_at < now - timedelta(days=1)
        )
    )
    token = secrets.token_urlsafe(32)
    row = SyncPairingCode(
        id=secrets.token_urlsafe(12),
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + timedelta(minutes=expires_in_minutes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return token, row


def pairing_attempt_for_address(db: Session, source_address: str) -> SyncPairingAttempt:
    """Lock and validate the shared PR6 pairing attempt window for this source address."""
    now = datetime.now(UTC)
    address_hash = hash_token(source_address or "unknown")
    db.execute(
        pg_insert(SyncPairingAttempt)
        .values(address_hash=address_hash, window_started_at=now, failed_attempts=0)
        .on_conflict_do_nothing(index_elements=[SyncPairingAttempt.address_hash])
    )
    attempt = db.scalar(
        select(SyncPairingAttempt)
        .where(SyncPairingAttempt.address_hash == address_hash)
        .with_for_update()
    )
    assert attempt is not None
    if attempt.blocked_until is not None and attempt.blocked_until > now:
        retry_after = max(1, math.ceil((attempt.blocked_until - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Ghép nối tạm khóa. Hãy thử lại sau 15 phút.",
            headers={"Retry-After": str(retry_after)},
        )
    if attempt.window_started_at < now - PAIRING_FAILURE_WINDOW:
        attempt.window_started_at = now
        attempt.failed_attempts = 0
        attempt.blocked_until = None
    return attempt


def record_failed_pairing_attempt(db: Session, attempt: SyncPairingAttempt) -> bool:
    """Count a bad credential and return whether the source is now locked out."""
    now = datetime.now(UTC)
    attempt.failed_attempts += 1
    if attempt.failed_attempts >= PAIRING_FAILURE_LIMIT:
        attempt.blocked_until = now + PAIRING_LOCKOUT
    return attempt.blocked_until is not None and attempt.blocked_until > now


def pair_device(
    db: Session, *, pairing_code: str, name: str, source_address: str
) -> tuple[SyncDevice, str]:
    now = datetime.now(UTC)
    attempt = pairing_attempt_for_address(db, source_address)

    code = db.scalar(
        select(SyncPairingCode)
        .where(SyncPairingCode.token_hash == hash_token(pairing_code))
        .with_for_update()
    )
    if (
        code is None
        or code.used_at is not None
        or code.revoked_at is not None
        or code.expires_at <= now
    ):
        blocked = record_failed_pairing_attempt(db, attempt)
        db.commit()
        raise HTTPException(
            status_code=429 if blocked else 401,
            detail=(
                "Ghép nối tạm khóa. Hãy thử lại sau 15 phút."
                if blocked
                else "Mã ghép nối không hợp lệ, đã dùng hoặc hết hạn."
            ),
            headers={"Retry-After": "900"} if blocked else None,
        )

    token = secrets.token_urlsafe(40)
    device = SyncDevice(name=name.strip(), token_hash=hash_token(token))
    code.used_at = now
    attempt.failed_attempts = 0
    attempt.blocked_until = None
    db.add(device)
    db.commit()
    db.refresh(device)
    return device, token


def get_device(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> SyncDevice:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401, detail="Thiếu token thiết bị.", headers={"WWW-Authenticate": "Bearer"}
        )
    device = db.scalar(
        select(SyncDevice).where(SyncDevice.token_hash == hash_token(credentials.credentials))
    )
    if device is None or device.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail="Token thiết bị không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from datetime import UTC, datetime

    device.last_seen_at = datetime.now(UTC)
    db.commit()
    return device
