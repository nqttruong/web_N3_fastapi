"""Database-backed batch jobs ("AI chữa các câu sai").

Each question is an item processed and saved independently; one failing item never fails the
others. Job status is derived from item statuses:

* any item pending/running        → pending (nothing started yet) / running
* all terminal, no failures       → completed (cached/succeeded/skipped)
* failures and at least one ok    → partial_failed
* failures and nothing ok         → failed
* cancelled by the user           → cancelled
"""

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.database.enums import JobItemStatus, JobStatus
from app.exams.models import Question
from app.explanations import service
from app.explanations.context import Ineligible, build_context
from app.explanations.models import ExplanationJob, ExplanationJobItem
from app.explanations.providers import registry
from app.explanations.schemas import JobItemRead, JobRead

TERMINAL_ITEMS = {
    JobItemStatus.CACHED,
    JobItemStatus.SUCCEEDED,
    JobItemStatus.FAILED,
    JobItemStatus.SKIPPED,
    JobItemStatus.CANCELLED,
}
ACTIVE_JOBS = (JobStatus.PENDING.value, JobStatus.RUNNING.value)


def refresh_status(job: ExplanationJob) -> None:
    if job.status == JobStatus.CANCELLED:
        if not any(i.status == JobItemStatus.RUNNING for i in job.items):
            job.finished_at = job.finished_at or utcnow()
        return
    counts = Counter(JobItemStatus(i.status) for i in job.items)
    if counts[JobItemStatus.PENDING] or counts[JobItemStatus.RUNNING]:
        started = counts[JobItemStatus.RUNNING] or any(
            JobItemStatus(i.status) in TERMINAL_ITEMS for i in job.items
        )
        job.status = (JobStatus.RUNNING if started else JobStatus.PENDING).value
        job.finished_at = None
        return
    ok = counts[JobItemStatus.CACHED] + counts[JobItemStatus.SUCCEEDED]
    if counts[JobItemStatus.FAILED]:
        job.status = (JobStatus.PARTIAL_FAILED if ok else JobStatus.FAILED).value
    else:
        job.status = JobStatus.COMPLETED.value
    job.finished_at = utcnow()


def to_read(db: Session, job: ExplanationJob) -> JobRead:
    numbers: dict[uuid.UUID, int] = dict(
        db.execute(  # type: ignore[arg-type]
            select(Question.id, Question.question_number).where(
                Question.id.in_([i.question_id for i in job.items])
            )
        ).all()
    )
    counts = Counter(i.status for i in job.items)
    return JobRead(
        id=job.id,
        attempt_id=job.attempt_id,
        status=JobStatus(job.status),
        force=job.force,
        counts={s.value: counts.get(s.value, 0) for s in JobItemStatus} | {"total": len(job.items)},
        items=[
            JobItemRead(
                id=i.id,
                question_id=i.question_id,
                question_number=numbers.get(i.question_id),
                attempt_answer_id=i.attempt_answer_id,
                status=JobItemStatus(i.status),
                tries=i.tries,
                error_code=i.error_code,
                error_message=i.error_message,
                explanation_id=i.explanation_id,
            )
            for i in job.items
        ],
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def get_job(db: Session, job_id: uuid.UUID) -> ExplanationJob:
    job = db.get(ExplanationJob, job_id)
    if job is None:
        raise NotFoundError("Không tìm thấy tác vụ chữa bài.", details={"job_id": str(job_id)})
    return job


def latest_for_attempt(db: Session, attempt_id: uuid.UUID) -> ExplanationJob | None:
    return db.scalar(
        select(ExplanationJob)
        .where(ExplanationJob.attempt_id == attempt_id)
        .order_by(ExplanationJob.created_at.desc())
        .limit(1)
    )


def create_batch(
    db: Session,
    settings: Settings,
    attempt_id: uuid.UUID,
    question_ids: list[uuid.UUID] | None,
    *,
    force: bool,
    idempotency_key: str | None,
) -> tuple[ExplanationJob, bool]:
    """Returns (job, created). Re-sending the same request returns the existing job."""
    if idempotency_key:
        existing = db.scalar(
            select(ExplanationJob).where(ExplanationJob.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.attempt_id != attempt_id:
                raise ConflictError("Idempotency-Key đã được dùng cho bài làm khác.")
            return existing, False
    if not registry.status(settings).available:
        raise service.AIUnavailableError(
            registry.status(settings).reason or "AI chưa được cấu hình.",
            details={"fallback": "manual"},
        )
    answers = service.attempt_answers(db, attempt_id)
    active = db.scalar(
        select(ExplanationJob)
        .where(ExplanationJob.attempt_id == attempt_id, ExplanationJob.status.in_(ACTIVE_JOBS))
        .with_for_update()
    )
    if active is not None:
        return active, False

    if question_ids is not None:
        wanted = set(question_ids)
        selected = [(a, q) for a, q in answers if q.id in wanted]
        unknown = wanted - {q.id for _, q in selected}
        if unknown:
            raise DomainValidationError(
                "Một số câu không thuộc bài làm này.",
                details={"question_ids": sorted(str(u) for u in unknown)},
            )
    else:
        selected = [(a, q) for a, q in answers if a.is_correct is False]
    if not selected:
        raise DomainValidationError("Không có câu nào để chữa (bài làm không có câu sai đã chấm).")
    if len(selected) > settings.ai_batch_max_questions:
        raise DomainValidationError(
            f"Tối đa {settings.ai_batch_max_questions} câu mỗi lần (AI_BATCH_MAX_QUESTIONS)."
        )

    job = ExplanationJob(
        attempt_id=attempt_id,
        status=JobStatus.PENDING.value,
        force=force,
        idempotency_key=idempotency_key,
    )
    for position, (answer, question) in enumerate(selected):
        ctx = build_context(db, question.id)
        item = ExplanationJobItem(
            question_id=question.id,
            attempt_answer_id=answer.id,
            position=position,
            status=JobItemStatus.PENDING.value,
        )
        if isinstance(ctx, Ineligible):
            item.status = JobItemStatus.SKIPPED.value
            item.error_code, item.error_message = ctx.code, ctx.message
        job.items.append(item)
    db.add(job)
    refresh_status(job)
    db.commit()
    return job, True


def retry_job(db: Session, settings: Settings, job_id: uuid.UUID) -> ExplanationJob:
    job = db.scalar(select(ExplanationJob).where(ExplanationJob.id == job_id).with_for_update())
    if job is None:
        raise NotFoundError("Không tìm thấy tác vụ chữa bài.")
    if job.status in ACTIVE_JOBS:
        raise ConflictError("Tác vụ đang chạy.")
    if not registry.status(settings).available:
        raise service.AIUnavailableError(
            registry.status(settings).reason or "AI chưa được cấu hình."
        )
    reopened = 0
    for item in job.items:
        if _should_reopen(db, item):
            item.status, item.error_code, item.error_message = (
                JobItemStatus.PENDING.value,
                None,
                None,
            )
            reopened += 1
    if not reopened:
        raise DomainValidationError("Không có câu lỗi nào để chạy lại.")
    job.status = JobStatus.PENDING.value
    job.finished_at = None
    refresh_status(job)
    db.commit()
    return job


def _should_reopen(db: Session, item: ExplanationJobItem) -> bool:
    if item.status in {JobItemStatus.FAILED.value, JobItemStatus.CANCELLED.value}:
        return True
    if item.status == JobItemStatus.SKIPPED.value:
        # The user may have confirmed the answer or linked the passage since.
        return not isinstance(build_context(db, item.question_id), Ineligible)
    return False


def cancel_job(db: Session, job_id: uuid.UUID) -> ExplanationJob:
    job = db.scalar(select(ExplanationJob).where(ExplanationJob.id == job_id).with_for_update())
    if job is None:
        raise NotFoundError("Không tìm thấy tác vụ chữa bài.")
    if job.status not in ACTIVE_JOBS:
        raise ConflictError("Tác vụ đã kết thúc.")
    for item in job.items:
        if item.status == JobItemStatus.PENDING.value:
            item.status = JobItemStatus.CANCELLED.value
    job.status = JobStatus.CANCELLED.value
    refresh_status(job)
    db.commit()
    return job
