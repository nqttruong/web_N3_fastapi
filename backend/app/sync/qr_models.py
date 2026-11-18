"""Web-side QR pairing sessions; legacy manual Android pairing stays intact."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SyncQRSession(Base):
    __tablename__ = "sync_qr_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    challenge_hash: Mapped[str] = mapped_column(Text, nullable=False)
    credential_hash: Mapped[str | None] = mapped_column(Text)
    claim_ticket_hash: Mapped[str | None] = mapped_column(Text)
    confirmation_hash: Mapped[str | None] = mapped_column(Text)
    device_name: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_devices.id", ondelete="RESTRICT")
    )
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED','WAITING_FOR_DEVICE','CLAIMED',"
            "'AWAITING_CONFIRMATION','PAIRED','EXPIRED',"
            "'REJECTED','CANCELLED','FAILED')",
            name="sync_qr_status_valid",
        ),
    )


class SyncQRAudit(Base):
    __tablename__ = "sync_qr_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_qr_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
