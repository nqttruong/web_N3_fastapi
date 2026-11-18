"""QR pairing session state machine without changing existing device pairing.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_qr_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("challenge_hash", sa.Text(), nullable=False),
        sa.Column("credential_hash", sa.Text()),
        sa.Column("claim_ticket_hash", sa.Text()),
        sa.Column("confirmation_hash", sa.Text()),
        sa.Column("device_name", sa.Text()),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_devices.id", ondelete="RESTRICT"),
        ),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('CREATED','WAITING_FOR_DEVICE','CLAIMED','AWAITING_CONFIRMATION','PAIRED','EXPIRED','REJECTED','CANCELLED','FAILED')",
            name="sync_qr_status_valid",
        ),
    )
    op.create_table(
        "sync_qr_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_qr_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sync_qr_audit")
    op.drop_table("sync_qr_sessions")
