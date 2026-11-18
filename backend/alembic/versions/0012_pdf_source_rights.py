"""Bind a private-use rights declaration to the exact PDF bytes.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("learning_source_rights", sa.Column("source_content_hash", sa.Text()))


def downgrade() -> None:
    op.drop_column("learning_source_rights", "source_content_hash")
