"""Remove stale import data: ``uv run python -m app.imports.cleanup [--dry-run]``.

* uncommitted drafts older than IMPORT_DRAFT_TTL_DAYS (and their files)
* screenshot files of committed drafts older than the TTL (the exam keeps the text; the
  draft row stays as an audit trail, its assets are removed)
* orphan directories in the storage root that have no draft row
"""

import argparse
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.database.enums import ImportStatus
from app.imports import storage
from app.imports.models import ImportAsset, ImportDraft


@dataclass
class CleanupReport:
    deleted_drafts: list[str] = field(default_factory=list)
    pruned_assets: int = 0
    orphan_dirs: list[str] = field(default_factory=list)


def run_cleanup(db: Session, settings: Settings, *, dry_run: bool = False) -> CleanupReport:
    report = CleanupReport()
    cutoff = utcnow() - timedelta(days=settings.import_draft_ttl_days)

    stale = list(
        db.scalars(
            select(ImportDraft).where(
                ImportDraft.status != ImportStatus.COMMITTED.value,
                ImportDraft.updated_at < cutoff,
            )
        )
    )
    for draft in stale:
        report.deleted_drafts.append(str(draft.id))
        if not dry_run:
            db.delete(draft)
            storage.delete_draft_dir(settings, draft.id)

    committed_old = list(
        db.scalars(
            select(ImportDraft.id).where(
                ImportDraft.status == ImportStatus.COMMITTED.value,
                ImportDraft.committed_at < cutoff,
            )
        )
    )
    for draft_id in committed_old:
        count = len(
            list(db.scalars(select(ImportAsset.id).where(ImportAsset.draft_id == draft_id)))
        )
        report.pruned_assets += count
        if count and not dry_run:
            db.execute(delete(ImportAsset).where(ImportAsset.draft_id == draft_id))
            storage.delete_draft_dir(settings, draft_id)

    known = {str(i) for i in db.scalars(select(ImportDraft.id))}
    for child in storage.root(settings).iterdir():
        if not child.is_dir():
            continue
        try:
            uuid.UUID(child.name)
        except ValueError:
            continue  # never touch anything we did not create
        if child.name not in known and child.name not in report.deleted_drafts:
            report.orphan_dirs.append(child.name)
            if not dry_run:
                shutil.rmtree(child, ignore_errors=True)

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    from app.database.session import get_sessionmaker

    with get_sessionmaker()() as db:
        report = run_cleanup(db, get_settings(), dry_run=args.dry_run)
    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}drafts deleted: {len(report.deleted_drafts)}, "
        f"assets pruned: {report.pruned_assets}, orphan dirs: {len(report.orphan_dirs)}"
    )


if __name__ == "__main__":
    main()
