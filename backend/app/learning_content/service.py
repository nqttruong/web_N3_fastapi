"""Transactional source scanning, licence filtering, upsert and audit operations."""

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.database.session import get_engine
from app.learning_content.models import (
    LearningContentChange,
    LearningContentPack,
    LearningExample,
    LearningItem,
    LearningItemExample,
    LearningLesson,
    LearningSyncRun,
)
from app.learning_content.schemas import (
    LearningItemPage,
    LearningItemRead,
    LearningPackRead,
    LearningSyncStatus,
    SyncRunRead,
)
from app.learning_content.source import (
    SourcePack,
    SourceRecord,
    SourceSnapshot,
    SourceValidationError,
    scan_source,
)
from app.learning_content.study_models import LearningSourceRight

ADVISORY_LOCK_KEY = 0x4E33594E43
MAX_ERROR_LENGTH = 2000
logger = logging.getLogger("learning_content_sync")


def enqueue_sync(db: Session, trigger: str, *, source_kind: str = "android") -> LearningSyncRun:
    if trigger not in {"startup", "interval", "manual"}:
        raise ValueError("Invalid learning content sync trigger")
    # Test cleanup and some operator-maintained environments can leave the singleton
    # table empty. Recreate its one row atomically before using it as the queue mutex.
    db.execute(
        text("""
            INSERT INTO learning_content_sync_queue_lock (id) VALUES (1)
            ON CONFLICT (id) DO NOTHING
        """)
    )
    db.execute(text("SELECT id FROM learning_content_sync_queue_lock WHERE id = 1 FOR UPDATE"))
    if source_kind not in {"android", "pdf"}:
        raise ValueError("Invalid learning content source kind")
    source_filter = (
        LearningSyncRun.source_commit_sha.like("pdf:%")
        if source_kind == "pdf"
        else or_(
            LearningSyncRun.source_commit_sha.is_(None),
            ~LearningSyncRun.source_commit_sha.like("pdf:%"),
        )
    )
    active = db.scalar(
        select(LearningSyncRun)
        .where(LearningSyncRun.status.in_(("queued", "running")), source_filter)
        .order_by(LearningSyncRun.requested_at)
        .limit(1)
    )
    if active is not None:
        return active
    run = LearningSyncRun(
        status="queued",
        trigger=trigger,
        source_commit_sha="pdf:pending" if source_kind == "pdf" else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def claim_and_process_one(sessions: sessionmaker[Session], settings: Settings) -> bool:
    """Process one queued run; a PostgreSQL advisory lock serializes all worker replicas."""
    lock_connection = get_engine().connect()
    acquired = False
    run_id: uuid.UUID | None = None
    db: Session | None = None
    try:
        acquired = bool(
            lock_connection.execute(select(func.pg_try_advisory_lock(ADVISORY_LOCK_KEY))).scalar()
        )
        lock_connection.commit()
        if not acquired:
            return False
        db = sessions()
        now = datetime.now(UTC)
        recover_stale_runs(db, settings.learning_content_sync_max_run_seconds, now)
        run = db.scalar(
            select(LearningSyncRun)
            .where(LearningSyncRun.status == "queued")
            .order_by(LearningSyncRun.requested_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            db.commit()
            return False
        run_id = run.id
        run.status = "running"
        run.started_at = now
        run.finished_at = None
        run.attempts += 1
        run.error = None
        db.commit()

        if (run.source_commit_sha or "").startswith("pdf:"):
            from app.learning_content.pdf_import import pdf_snapshot

            snapshot = pdf_snapshot(db, settings)
            counts = apply_snapshot(db, run_id, snapshot, settings, managed_path_prefix="pdf:")
        else:
            if settings.android_learning_source_dir is None:
                raise SourceValidationError("ANDROID_LEARNING_SOURCE_DIR chưa được cấu hình")
            permitted = set(
                db.execute(
                    select(LearningSourceRight.pack_id, LearningSourceRight.source_id).where(
                        LearningSourceRight.approved.is_(True),
                        LearningSourceRight.scope == "private",
                    )
                )
                .tuples()
                .all()
            )
            snapshot = scan_source(settings.android_learning_source_dir, permitted)
            counts = apply_snapshot(db, run_id, snapshot, settings)
        db.commit()
        completed_run = db.get(LearningSyncRun, run_id)
        logger.info(
            "Learning content run %s completed: status=%s source_commit=%s counts=%s",
            run_id,
            completed_run.status if completed_run is not None else "unknown",
            snapshot.commit_sha,
            counts,
        )
        return True
    except Exception as exc:
        logger.exception("Learning content sync run %s failed", run_id)
        if db is not None:
            db.rollback()
        if db is not None and run_id is not None:
            run = db.get(LearningSyncRun, run_id)
            if run is not None:
                run.error = str(exc)[:MAX_ERROR_LENGTH]
                run.finished_at = datetime.now(UTC)
                run.status = "queued" if run.attempts < 3 else "failed"
                db.commit()
        return True
    finally:
        if acquired:
            try:
                lock_connection.execute(select(func.pg_advisory_unlock(ADVISORY_LOCK_KEY)))
                lock_connection.commit()
            except Exception:
                lock_connection.rollback()
        if db is not None:
            db.close()
        lock_connection.close()


def recover_stale_runs(db: Session, max_run_seconds: int, now: datetime | None = None) -> None:
    """Requeue an interrupted worker run, or fail it after its bounded retries."""
    current = now or datetime.now(UTC)
    stale_before = current.timestamp() - max_run_seconds
    db.execute(
        text("""
            UPDATE learning_content_sync_runs
            SET status = CASE WHEN attempts < 3 THEN 'queued' ELSE 'failed' END,
                error = COALESCE(error, 'Worker restarted before the previous run completed'),
                finished_at = :now
            WHERE status = 'running' AND started_at < to_timestamp(:stale_before)
        """),
        {"stale_before": stale_before, "now": current},
    )


def apply_snapshot(
    db: Session,
    run_id: uuid.UUID,
    snapshot: SourceSnapshot,
    settings: Settings,
    *,
    managed_path_prefix: str = "app/src/main/assets/content/",
) -> dict[str, int]:
    """Validate an entire scanned source first, then apply all source changes atomically."""
    db.execute(
        text(f"SET LOCAL statement_timeout = '{settings.learning_content_sync_max_run_seconds}s'")
    )
    counts: Counter[str] = Counter()
    current_paths = {pack.relative_path for pack in snapshot.packs}
    previous_packs = list(
        db.scalars(
            select(LearningContentPack).where(
                LearningContentPack.is_archived.is_(False),
                LearningContentPack.source_path.like(f"{managed_path_prefix}%"),
            )
        )
    )

    source_path_owners = {pack.source_path: pack.id for pack in previous_packs}
    for source_pack in snapshot.packs:
        owner = source_path_owners.get(source_pack.relative_path)
        if owner is not None and owner != source_pack.pack_id:
            raise SourceValidationError(
                f"Source path đã thuộc pack khác ({source_pack.relative_path}: {owner})"
            )

    for source_pack in snapshot.packs:
        _upsert_pack(db, run_id, source_pack, counts)
    for old_pack in previous_packs:
        if old_pack.source_path not in current_paths:
            _archive_pack(db, run_id, old_pack, counts)

    db.get(LearningSyncRun, run_id).source_commit_sha = snapshot.commit_sha  # type: ignore[union-attr]
    db.get(LearningSyncRun, run_id).source_manifest_hash = snapshot.manifest_hash  # type: ignore[union-attr]
    has_changes = any(value for key, value in counts.items() if key != "license_blocked")
    run = db.get(LearningSyncRun, run_id)
    assert run is not None
    run.counts = dict(counts)
    run.status = "succeeded" if has_changes else "no_changes"
    run.finished_at = datetime.now(UTC)
    return dict(counts)


def _record_change(
    db: Session,
    run_id: uuid.UUID,
    *,
    pack_id: str,
    entity_type: str,
    source_ref: str,
    change_type: str,
    old_hash: str | None = None,
    new_hash: str | None = None,
    source_version: int | None = None,
) -> None:
    db.add(
        LearningContentChange(
            run_id=run_id,
            pack_id=pack_id,
            entity_type=entity_type,
            source_ref=source_ref,
            change_type=change_type,
            old_hash=old_hash,
            new_hash=new_hash,
            source_version=source_version,
        )
    )


def _upsert_pack(db: Session, run_id: uuid.UUID, source: SourcePack, counts: Counter[str]) -> None:
    pack = db.get(LearningContentPack, source.pack_id)
    created = pack is None
    old_hash = pack.source_hash if pack else None
    if pack is None:
        pack = LearningContentPack(
            id=source.pack_id,
            title=source.title,
            jlpt_level=source.jlpt_level,
            source_path=source.relative_path,
            source_version=source.version,
            source_hash=source.source_hash,
            source_commit_sha=source.source_commit_sha,
            source_manifest_hash=source.source_manifest_hash,
            license_blocked_count=source.blocked_count,
            is_archived=False,
        )
        db.add(pack)
        counts["new_packs"] += 1
    else:
        if pack.source_path != source.relative_path:
            other = db.scalar(
                select(LearningContentPack).where(
                    LearningContentPack.source_path == source.relative_path,
                    LearningContentPack.id != source.pack_id,
                )
            )
            if other:
                raise SourceValidationError(f"Source path conflict: {source.relative_path}")
        if pack.source_hash != source.source_hash:
            counts["changed_packs"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type="pack",
                source_ref=source.pack_id,
                change_type="updated",
                old_hash=old_hash,
                new_hash=source.source_hash,
                source_version=source.version,
            )
        pack.title = source.title
        pack.jlpt_level = source.jlpt_level
        pack.source_path = source.relative_path
        pack.source_version = source.version
        pack.source_hash = source.source_hash
        pack.source_commit_sha = source.source_commit_sha
        pack.source_manifest_hash = source.source_manifest_hash
        pack.license_blocked_count = source.blocked_count
        if pack.is_archived:
            pack.is_archived = False
            counts["restored_packs"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type="pack",
                source_ref=source.pack_id,
                change_type="restored",
                new_hash=source.source_hash,
                source_version=source.version,
            )
        else:
            pack.synced_at = datetime.now(UTC)
    db.flush()
    if created:
        _record_change(
            db,
            run_id,
            pack_id=source.pack_id,
            entity_type="pack",
            source_ref=source.pack_id,
            change_type="created",
            new_hash=source.source_hash,
            source_version=source.version,
        )
    counts["license_blocked"] += source.blocked_count
    pack.synced_at = datetime.now(UTC)
    db.flush()

    desired_lesson_ids = {lesson.source_id for lesson in source.lessons}
    existing_lessons = list(
        db.scalars(select(LearningLesson).where(LearningLesson.pack_id == source.pack_id))
    )
    existing_lesson_by_id = {lesson.source_id: lesson for lesson in existing_lessons}
    for lesson_src in source.lessons:
        lesson = existing_lesson_by_id.get(lesson_src.source_id)
        if lesson is None:
            lesson = LearningLesson(
                id=lesson_src.stable_id,
                pack_id=source.pack_id,
                source_id=lesson_src.source_id,
                number=lesson_src.number,
                order_index=lesson_src.order_index,
                title=lesson_src.title,
                description=lesson_src.description,
                is_archived=False,
            )
            db.add(lesson)
            counts["new_lessons"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type="lesson",
                source_ref=lesson.source_id,
                change_type="created",
                source_version=source.version,
            )
        else:
            changed = (lesson.number, lesson.order_index, lesson.title, lesson.description) != (
                lesson_src.number,
                lesson_src.order_index,
                lesson_src.title,
                lesson_src.description,
            )
            if changed:
                counts["changed_lessons"] += 1
                _record_change(
                    db,
                    run_id,
                    pack_id=source.pack_id,
                    entity_type="lesson",
                    source_ref=lesson.source_id,
                    change_type="updated",
                    source_version=source.version,
                )
            if lesson.is_archived:
                counts["restored_lessons"] += 1
                _record_change(
                    db,
                    run_id,
                    pack_id=source.pack_id,
                    entity_type="lesson",
                    source_ref=lesson.source_id,
                    change_type="restored",
                    source_version=source.version,
                )
            lesson.number = lesson_src.number
            lesson.order_index = lesson_src.order_index
            lesson.title = lesson_src.title
            lesson.description = lesson_src.description
            lesson.is_archived = False
        db.flush()

    lesson_ids_by_source = {lesson.source_id: lesson.stable_id for lesson in source.lessons}
    for lesson_src in source.lessons:
        lesson_id = lesson_ids_by_source[lesson_src.source_id]
        _upsert_examples(db, run_id, source, lesson_src.content_items, counts)
        for record in lesson_src.content_items:
            _upsert_item(db, run_id, source, lesson_id, record, counts)

    db.flush()
    _archive_missing_rows(db, run_id, source, desired_lesson_ids, counts)


def _upsert_examples(
    db: Session,
    run_id: uuid.UUID,
    pack: SourcePack,
    records: tuple[SourceRecord, ...],
    counts: Counter[str],
) -> None:
    wanted = {ref for record in records for ref in record.example_refs}
    examples_by_ref = {
        example.source_ref: example for example in pack.examples if example.source_ref in wanted
    }
    for ref in wanted:
        if ref not in examples_by_ref:
            raise SourceValidationError(
                f"Licensed item references missing/blocked example: {pack.pack_id}/{ref}"
            )
    for example in examples_by_ref.values():
        row = db.scalar(
            select(LearningExample).where(
                LearningExample.pack_id == pack.pack_id,
                LearningExample.source_ref == example.source_ref,
            )
        )
        if row is None:
            db.add(
                LearningExample(
                    id=example.stable_id,
                    pack_id=pack.pack_id,
                    source_id=example.source_id,
                    source_ref=example.source_ref,
                    content_hash=example.content_hash,
                    source_version=pack.version,
                    payload=example.payload,
                    is_archived=False,
                )
            )
            counts["new_examples"] += 1
            _record_change(
                db,
                run_id,
                pack_id=pack.pack_id,
                entity_type="example",
                source_ref=example.source_ref,
                change_type="created",
                new_hash=example.content_hash,
                source_version=pack.version,
            )
        else:
            if row.content_hash != example.content_hash:
                counts["changed_examples"] += 1
                _record_change(
                    db,
                    run_id,
                    pack_id=pack.pack_id,
                    entity_type="example",
                    source_ref=example.source_ref,
                    change_type="updated",
                    old_hash=row.content_hash,
                    new_hash=example.content_hash,
                    source_version=pack.version,
                )
            if row.is_archived:
                counts["restored_examples"] += 1
                _record_change(
                    db,
                    run_id,
                    pack_id=pack.pack_id,
                    entity_type="example",
                    source_ref=example.source_ref,
                    change_type="restored",
                    new_hash=example.content_hash,
                    source_version=pack.version,
                )
            row.source_id = example.source_id
            row.content_hash = example.content_hash
            row.source_version = pack.version
            row.payload = example.payload
            row.is_archived = False


def _upsert_item(
    db: Session,
    run_id: uuid.UUID,
    pack: SourcePack,
    lesson_id: uuid.UUID,
    record: SourceRecord,
    counts: Counter[str],
) -> None:
    row = db.scalar(
        select(LearningItem).where(
            LearningItem.pack_id == pack.pack_id,
            LearningItem.item_type == record.entity_type,
            LearningItem.source_ref == record.source_ref,
        )
    )
    if row is None:
        row = LearningItem(
            id=record.stable_id,
            pack_id=pack.pack_id,
            lesson_id=lesson_id,
            item_type=record.entity_type,
            source_ref=record.source_ref,
            jlpt_level=pack.jlpt_level,
            order_index=record.order_index,
            source_version=pack.version,
            content_hash=record.content_hash,
            source_id=record.source_id,
            source_name=record.source_name,
            source_license=record.source_license,
            payload=record.payload,
            is_archived=False,
        )
        db.add(row)
        db.flush()
        counts[f"new_{record.entity_type}"] += 1
        _record_change(
            db,
            run_id,
            pack_id=pack.pack_id,
            entity_type=record.entity_type,
            source_ref=record.source_ref,
            change_type="created",
            new_hash=record.content_hash,
            source_version=pack.version,
        )
    else:
        if row.content_hash != record.content_hash:
            counts[f"changed_{record.entity_type}"] += 1
            _record_change(
                db,
                run_id,
                pack_id=pack.pack_id,
                entity_type=record.entity_type,
                source_ref=record.source_ref,
                change_type="updated",
                old_hash=row.content_hash,
                new_hash=record.content_hash,
                source_version=pack.version,
            )
        if row.is_archived:
            counts[f"restored_{record.entity_type}"] += 1
            _record_change(
                db,
                run_id,
                pack_id=pack.pack_id,
                entity_type=record.entity_type,
                source_ref=record.source_ref,
                change_type="restored",
                new_hash=record.content_hash,
                source_version=pack.version,
            )
        row.lesson_id = lesson_id
        row.jlpt_level = pack.jlpt_level
        row.order_index = record.order_index
        row.source_version = pack.version
        row.content_hash = record.content_hash
        row.source_id = record.source_id
        row.source_name = record.source_name
        row.source_license = record.source_license
        row.payload = record.payload
        row.is_archived = False
        db.flush()

    db.query(LearningItemExample).filter(LearningItemExample.item_id == row.id).delete(
        synchronize_session=False
    )
    for index, ref in enumerate(record.example_refs):
        example = db.scalar(
            select(LearningExample).where(
                LearningExample.pack_id == pack.pack_id,
                LearningExample.source_ref == ref,
            )
        )
        if example is None or example.is_archived:
            raise SourceValidationError(f"Example FK unavailable: {pack.pack_id}/{ref}")
        db.add(
            LearningItemExample(
                pack_id=pack.pack_id,
                item_id=row.id,
                example_id=example.id,
                order_index=index,
            )
        )


def _archive_missing_rows(
    db: Session,
    run_id: uuid.UUID,
    source: SourcePack,
    desired_lessons: set[str],
    counts: Counter[str],
) -> None:
    desired_items = {
        (record.entity_type, record.source_ref)
        for lesson in source.lessons
        for record in lesson.content_items
    }
    desired_examples = {
        ref
        for lesson in source.lessons
        for record in lesson.content_items
        for ref in record.example_refs
    }
    for item in db.scalars(select(LearningItem).where(LearningItem.pack_id == source.pack_id)):
        if not item.is_archived and (item.item_type, item.source_ref) not in desired_items:
            item.is_archived = True
            counts[f"archived_{item.item_type}"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type=item.item_type,
                source_ref=item.source_ref,
                change_type="archived",
                old_hash=item.content_hash,
                source_version=source.version,
            )
    for lesson in db.scalars(
        select(LearningLesson).where(LearningLesson.pack_id == source.pack_id)
    ):
        if not lesson.is_archived and lesson.source_id not in desired_lessons:
            lesson.is_archived = True
            counts["archived_lessons"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type="lesson",
                source_ref=lesson.source_id,
                change_type="archived",
                source_version=source.version,
            )
    for example in db.scalars(
        select(LearningExample).where(LearningExample.pack_id == source.pack_id)
    ):
        if not example.is_archived and example.source_ref not in desired_examples:
            example.is_archived = True
            counts["archived_examples"] += 1
            _record_change(
                db,
                run_id,
                pack_id=source.pack_id,
                entity_type="example",
                source_ref=example.source_ref,
                change_type="archived",
                old_hash=example.content_hash,
                source_version=source.version,
            )


def _archive_pack(
    db: Session, run_id: uuid.UUID, pack: LearningContentPack, counts: Counter[str]
) -> None:
    pack.is_archived = True
    pack.source_path = f"archived/{pack.id}/{pack.source_path}"
    _record_change(
        db,
        run_id,
        pack_id=pack.id,
        entity_type="pack",
        source_ref=pack.id,
        change_type="archived",
        old_hash=pack.source_hash,
        source_version=pack.source_version,
    )
    counts["archived_packs"] += 1
    for row in db.scalars(
        select(LearningItem).where(
            LearningItem.pack_id == pack.id, LearningItem.is_archived.is_(False)
        )
    ):
        row.is_archived = True
        counts[f"archived_{row.item_type}"] += 1
        _record_change(
            db,
            run_id,
            pack_id=pack.id,
            entity_type=row.item_type,
            source_ref=row.source_ref,
            change_type="archived",
            old_hash=row.content_hash,
            source_version=pack.source_version,
        )
    for lesson_row in db.scalars(
        select(LearningLesson).where(
            LearningLesson.pack_id == pack.id, LearningLesson.is_archived.is_(False)
        )
    ):
        lesson_row.is_archived = True
        counts["archived_lessons"] += 1
        _record_change(
            db,
            run_id,
            pack_id=pack.id,
            entity_type="lesson",
            source_ref=lesson_row.source_id,
            change_type="archived",
            source_version=pack.source_version,
        )
    for example_row in db.scalars(
        select(LearningExample).where(
            LearningExample.pack_id == pack.id, LearningExample.is_archived.is_(False)
        )
    ):
        example_row.is_archived = True
        counts["archived_examples"] += 1
        _record_change(
            db,
            run_id,
            pack_id=pack.id,
            entity_type="example",
            source_ref=example_row.source_ref,
            change_type="archived",
            old_hash=example_row.content_hash,
            source_version=pack.source_version,
        )


def sync_status(db: Session, settings: Settings) -> LearningSyncStatus:
    latest = db.scalar(
        select(LearningSyncRun).order_by(LearningSyncRun.requested_at.desc()).limit(1)
    )
    last_success = db.scalar(
        select(LearningSyncRun)
        .where(LearningSyncRun.status.in_(("succeeded", "no_changes")))
        .order_by(LearningSyncRun.finished_at.desc())
        .limit(1)
    )
    packs = list(
        db.execute(
            select(LearningContentPack, func.count(LearningItem.id))
            .outerjoin(
                LearningItem,
                (LearningItem.pack_id == LearningContentPack.id)
                & LearningItem.is_archived.is_(False),
            )
            .group_by(LearningContentPack.id)
            .order_by(LearningContentPack.jlpt_level, LearningContentPack.title)
        )
    )
    pack_reads = [
        LearningPackRead(
            id=pack.id,
            title=pack.title,
            jlpt_level=pack.jlpt_level,
            source_version=pack.source_version,
            source_commit_sha=pack.source_commit_sha,
            license_blocked_count=pack.license_blocked_count,
            active_item_count=count,
            synced_at=pack.synced_at,
            is_archived=pack.is_archived,
        )
        for pack, count in packs
    ]
    grouped = db.execute(
        select(LearningItem.item_type, func.count(LearningItem.id))
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(LearningItem.is_archived.is_(False), LearningContentPack.is_archived.is_(False))
        .group_by(LearningItem.item_type)
    )
    active_counts = {item_type: count for item_type, count in grouped}
    for item_type in ("vocabulary", "kanji", "grammar"):
        active_counts.setdefault(item_type, 0)
    configured_path = settings.android_learning_source_dir
    return LearningSyncStatus(
        source_configured=configured_path is not None,
        source_available=bool(configured_path and configured_path.is_dir()),
        source_description="Git-tracked Android content assets (read-only)",
        interval_minutes=settings.learning_content_sync_interval_minutes,
        last_checked_at=latest.finished_at if latest else None,
        last_success_at=last_success.finished_at if last_success else None,
        current_versions=pack_reads,
        active_counts=active_counts,
        last_run=SyncRunRead.model_validate(latest, from_attributes=True) if latest else None,
    )


def learning_items(
    db: Session,
    *,
    item_type: str | None,
    jlpt_level: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> LearningItemPage:
    stmt = (
        select(LearningItem, LearningLesson, LearningContentPack)
        .join(LearningLesson, LearningLesson.id == LearningItem.lesson_id)
        .join(LearningContentPack, LearningContentPack.id == LearningItem.pack_id)
        .where(
            LearningItem.is_archived.is_(False),
            LearningLesson.is_archived.is_(False),
            LearningContentPack.is_archived.is_(False),
        )
    )
    if item_type:
        stmt = stmt.where(LearningItem.item_type == item_type)
    if jlpt_level:
        stmt = stmt.where(LearningItem.jlpt_level == jlpt_level)
    if q:
        pattern = f"%{q.strip()}%"
        searchable = [
            LearningItem.payload[key].astext.ilike(pattern)
            for key in ("expression", "reading", "meaningVi", "character", "pattern", "structure")
        ]
        stmt = stmt.where(or_(*searchable))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.execute(
            stmt.order_by(
                LearningItem.jlpt_level,
                LearningContentPack.title,
                LearningLesson.order_index,
                LearningItem.order_index,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    ids = [item.id for item, _, _ in rows]
    example_map: dict[uuid.UUID, list[dict[str, Any]]] = {item_id: [] for item_id in ids}
    if ids:
        examples = db.execute(
            select(LearningItemExample.item_id, LearningExample.payload)
            .join(LearningExample, LearningExample.id == LearningItemExample.example_id)
            .where(LearningItemExample.item_id.in_(ids), LearningExample.is_archived.is_(False))
            .order_by(LearningItemExample.order_index)
        )
        for item_id, payload in examples:
            example_map[item_id].append(payload)
    items = [
        LearningItemRead(
            id=item.id,
            stable_source_id=f"{item.pack_id}:{item.item_type}:{item.source_ref}",
            item_type=item.item_type,
            jlpt_level=item.jlpt_level,
            pack_id=item.pack_id,
            pack_title=pack.title,
            source_version=item.source_version,
            lesson_id=lesson.source_id,
            lesson_number=lesson.number,
            lesson_title=lesson.title,
            order_index=item.order_index,
            source_name=item.source_name,
            source_license=item.source_license,
            payload=item.payload,
            examples=example_map[item.id],
        )
        for item, lesson, pack in rows
    ]
    return LearningItemPage(items=items, total=total, page=page, page_size=page_size)
