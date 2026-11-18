"""Add one-time pairing codes and per-device pull/push activity.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sync_devices", sa.Column("last_pull_at", sa.DateTime(timezone=True)))
    op.add_column("sync_devices", sa.Column("last_push_at", sa.DateTime(timezone=True)))

    op.create_table(
        "sync_pairing_codes",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_sync_pairing_code_expiry")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_pairing_codes")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sync_pairing_codes_token_hash")),
    )
    op.create_index("ix_sync_pairing_codes_expiry", "sync_pairing_codes", ["expires_at"])

    op.create_table(
        "sync_pairing_attempts",
        sa.Column("address_hash", sa.Text(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "failed_attempts >= 0", name=op.f("ck_sync_pairing_attempts_nonnegative")
        ),
        sa.PrimaryKeyConstraint("address_hash", name=op.f("pk_sync_pairing_attempts")),
    )


def downgrade() -> None:
    op.drop_table("sync_pairing_attempts")
    op.drop_index("ix_sync_pairing_codes_expiry", table_name="sync_pairing_codes")
    op.drop_table("sync_pairing_codes")
    op.drop_column("sync_devices", "last_push_at")
    op.drop_column("sync_devices", "last_pull_at")
