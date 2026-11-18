"""Dedicated, single-instance learning sync worker.

Run with ``python -m app.learning_content.worker``.
"""

import logging
import signal
import time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.database.session import get_engine, get_sessionmaker
from app.learning_content.service import claim_and_process_one, enqueue_sync

logger = logging.getLogger("learning_content_sync")
SCHEDULER_LOCK_KEY = 0x4E335343484544


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    source = settings.android_learning_source_dir
    if source is None or not source.is_dir():
        logger.error("Android learning source path is unavailable; worker exits without syncing")
        raise SystemExit(2)

    sessions = get_sessionmaker()
    lock_connection = get_engine().connect()
    locked = bool(
        lock_connection.execute(select(func.pg_try_advisory_lock(SCHEDULER_LOCK_KEY))).scalar()
    )
    lock_connection.commit()
    if not locked:
        logger.error("Another learning content scheduler holds the singleton lock; exiting")
        lock_connection.close()
        raise SystemExit(3)

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    interval = settings.learning_content_sync_interval_minutes * 60
    logger.info("Learning content worker started; interval=%s minutes", interval // 60)
    try:
        with sessions() as db:
            enqueue_sync(db, "startup")
        next_interval = time.monotonic() + interval
        while running:
            processed = claim_and_process_one(sessions, settings)
            if processed:
                continue
            now = time.monotonic()
            if now >= next_interval:
                with sessions() as db:
                    enqueue_sync(db, "interval")
                next_interval = now + interval
            time.sleep(1)
    finally:
        try:
            lock_connection.execute(select(func.pg_advisory_unlock(SCHEDULER_LOCK_KEY)))
            lock_connection.commit()
        finally:
            lock_connection.close()
        logger.info("Learning content worker stopped")


if __name__ == "__main__":
    main()
