"""Add structured browser-capture drafts and retry idempotency.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_import_drafts_method_valid"), "import_drafts", type_="check")
    op.create_check_constraint(
        op.f("ck_import_drafts_method_valid"),
        "import_drafts",
        "method IN ('text', 'html', 'images', 'browser_capture')",
    )
    op.create_index(
        "uq_import_drafts_browser_capture_retry",
        "import_drafts",
        ["raw_sha256"],
        unique=True,
        postgresql_where=sa.text("method = 'browser_capture'"),
    )


def downgrade() -> None:
    op.drop_index("uq_import_drafts_browser_capture_retry", table_name="import_drafts")
    op.drop_constraint(op.f("ck_import_drafts_method_valid"), "import_drafts", type_="check")
    op.create_check_constraint(
        op.f("ck_import_drafts_method_valid"),
        "import_drafts",
        "method IN ('text', 'html', 'images')",
    )
