"""Local, database-backed worker for explanation jobs.

* Items are claimed with ``FOR UPDATE SKIP LOCKED`` and a lease; state lives only in the DB.
* On start-up every ``running`` item is returned to ``pending`` (the previous process died);
  while running, items whose lease expired are recovered too.
* Concurrency is bounded by AI_MAX_CONCURRENT_REQUESTS (thread pool + provider semaphore).

Runs inside the API process (FastAPI lifespan) or standalone:
``uv run python -m app.explanations.worker``.
"""

import contextlib
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.database.enums import JobItemStatus, JobStatus
from app.explanations import jobs, service
from app.explanations.models import ExplanationJob, ExplanationJobItem
from app.explanations.service import GenerationInProgressError, IneligibleError

logger = logging.getLogger(__name__)


def lease_duration(settings: Settings) -> timedelta:
    calls = (settings.ai_max_retries + 1) * (settings.ai_max_format_retries + 1)
    return timedelta(seconds=settings.ai_request_timeout * calls + 120)


class ExplanationWorker:
    def __init__(self, factory: sessionmaker[Session], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings
        self.concurrency = settings.ai_max_concurrent_requests
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ recovery
    def recover(self, *, all_running: bool = False) -> int:
        with self.factory() as db:
            conds = [ExplanationJobItem.status == JobItemStatus.RUNNING.value]
            if not all_running:
                conds.append(
                    or_(
                        ExplanationJobItem.lease_expires_at.is_(None),
                        ExplanationJobItem.lease_expires_at < utcnow(),
                    )
                )
            result = db.execute(
                update(ExplanationJobItem)
                .where(*conds)
                .values(status=JobItemStatus.PENDING.value, lease_expires_at=None)
            )
            db.commit()
            count = int(result.rowcount or 0)  # type: ignore[attr-defined]
        if count:
            logger.info("Recovered %d interrupted explanation item(s)", count)
        return count

    # ------------------------------------------------------------ claiming
    def claim(self, limit: int) -> list[uuid.UUID]:
        with self.factory() as db:
            candidates = (
                select(ExplanationJobItem.id)
                .join(ExplanationJob, ExplanationJob.id == ExplanationJobItem.job_id)
                .where(
                    ExplanationJobItem.status == JobItemStatus.PENDING.value,
                    ExplanationJob.status != JobStatus.CANCELLED.value,
                )
                .order_by(ExplanationJob.created_at, ExplanationJobItem.position)
                .limit(limit)
                .with_for_update(of=ExplanationJobItem, skip_locked=True)
            )
            ids = list(db.scalars(candidates))
            if not ids:
                return []
            now = utcnow()
            db.execute(
                update(ExplanationJobItem)
                .where(ExplanationJobItem.id.in_(ids))
                .values(
                    status=JobItemStatus.RUNNING.value,
                    lease_expires_at=now + lease_duration(self.settings),
                    tries=ExplanationJobItem.tries + 1,
                )
            )
            for job in db.scalars(
                select(ExplanationJob)
                .join(ExplanationJobItem, ExplanationJobItem.job_id == ExplanationJob.id)
                .where(ExplanationJobItem.id.in_(ids))
                .distinct()
            ):
                job.started_at = job.started_at or now
                jobs.refresh_status(job)
            db.commit()
            return ids

    # ------------------------------------------------------------ processing
    def process(self, item_id: uuid.UUID) -> None:
        with self.factory() as db:
            item = db.get(ExplanationJobItem, item_id)
            if item is None or item.status != JobItemStatus.RUNNING.value:
                return
            job = item.job
            try:
                if job.status == JobStatus.CANCELLED:
                    item.status = JobItemStatus.CANCELLED.value
                else:
                    outcome = service.generate_for_question(
                        db, self.settings, item.question_id,
                        force=job.force, attempt_answer_id=item.attempt_answer_id,
                    )  # fmt: skip
                    item.explanation_id = outcome.explanation.id
                    item.status = (
                        JobItemStatus.CACHED
                        if outcome.kind == "cached"
                        else JobItemStatus.SUCCEEDED
                    ).value
                    item.error_code = item.error_message = None
            except GenerationInProgressError:
                db.rollback()
                item = db.get(ExplanationJobItem, item_id)
                assert item is not None
                item.status = JobItemStatus.PENDING.value  # someone else is generating it
            except IneligibleError as exc:
                db.rollback()
                item = db.get(ExplanationJobItem, item_id)
                assert item is not None
                item.status = JobItemStatus.SKIPPED.value
                item.error_code = str((exc.details or {}).get("reason", exc.code))
                item.error_message = exc.message
            except AppError as exc:
                db.rollback()
                item = db.get(ExplanationJobItem, item_id)
                assert item is not None
                item.status = JobItemStatus.FAILED.value
                details = exc.details if isinstance(exc.details, dict) else {}
                item.error_code = str(details.get("provider_code") or exc.code)
                item.error_message = exc.message
            except Exception:
                logger.exception("Unexpected error processing explanation item %s", item_id)
                db.rollback()
                item = db.get(ExplanationJobItem, item_id)
                assert item is not None
                item.status = JobItemStatus.FAILED.value
                item.error_code, item.error_message = "internal_error", "Lỗi không mong muốn."
            item.lease_expires_at = None
            refreshed = db.get(ExplanationJob, item.job_id)
            assert refreshed is not None
            db.flush()
            db.refresh(refreshed)
            jobs.refresh_status(refreshed)
            db.commit()

    def run_once(self, executor: ThreadPoolExecutor | None = None) -> int:
        self.recover()
        ids = self.claim(self.concurrency)
        if executor is None:
            for item_id in ids:
                self.process(item_id)
        else:
            list(executor.map(self.process, ids))
        return len(ids)

    # ------------------------------------------------------------ lifecycle
    def _loop(self) -> None:
        self.recover(all_running=True)
        with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="ai") as pool:
            while not self._stop.is_set():
                try:
                    processed = self.run_once(pool)
                except Exception:
                    logger.exception("Explanation worker iteration failed")
                    processed = 0
                if not processed:
                    self._stop.wait(self.settings.ai_worker_poll_seconds)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._loop, name="explanation-worker", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)


def main() -> None:
    from app.database.session import get_sessionmaker

    logging.basicConfig(level=logging.INFO)
    worker = ExplanationWorker(get_sessionmaker(), get_settings())
    worker.recover(all_running=True)
    logger.info("Explanation worker started (concurrency=%d)", worker.concurrency)
    with contextlib.suppress(KeyboardInterrupt):
        worker._loop()


if __name__ == "__main__":
    main()
