"""Provider call log (tokens, estimated cost) and budget guards.

Each call is recorded in its own transaction, so failed calls still count against the budget.
Prompt and response content are never stored here.
"""

import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.database.enums import AIRequestStatus
from app.explanations.interfaces import Usage
from app.explanations.models import AIRequest


class BudgetExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "ai_budget_exceeded"


def estimate_cost(settings: Settings, usage: Usage) -> Decimal | None:
    pin, pout = settings.ai_price_input_per_1m_tokens, settings.ai_price_output_per_1m_tokens
    if pin is None or pout is None or usage.input_tokens is None or usage.output_tokens is None:
        return None
    cost = (usage.input_tokens * pin + usage.output_tokens * pout) / 1_000_000
    return Decimal(str(round(cost, 6)))


def record(
    db: Session,
    settings: Settings,
    *,
    provider: str,
    model: str,
    question_id: uuid.UUID | None,
    ok: bool,
    error_code: str | None,
    usage: Usage | None,
    duration_ms: int,
) -> Decimal | None:
    usage = usage or Usage()
    cost = estimate_cost(settings, usage)
    factory = sessionmaker(bind=db.get_bind())
    with factory() as log_db:  # independent transaction
        log_db.add(
            AIRequest(
                provider=provider,
                model=model,
                question_id=question_id,
                status=(AIRequestStatus.SUCCEEDED if ok else AIRequestStatus.FAILED).value,
                error_code=error_code,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=cost,
                duration_ms=duration_ms,
            )
        )
        log_db.commit()
    return cost


def _start_of_day(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Spending:
    requests_today: int
    month_cost_usd: float
    month_input_tokens: int
    month_output_tokens: int


def spending(db: Session) -> Spending:
    now = utcnow()
    month_start = _start_of_day(now).replace(day=1)
    day_start = _start_of_day(now)
    month_cost, month_in, month_out = db.execute(
        select(
            func.coalesce(func.sum(AIRequest.cost_usd), 0),
            func.coalesce(func.sum(AIRequest.input_tokens), 0),
            func.coalesce(func.sum(AIRequest.output_tokens), 0),
        ).where(AIRequest.created_at >= month_start)
    ).one()
    today = db.scalar(select(func.count(AIRequest.id)).where(AIRequest.created_at >= day_start))
    return Spending(int(today or 0), float(month_cost), int(month_in), int(month_out))


def check_budget(db: Session, settings: Settings) -> None:
    spent = spending(db)
    if spent.requests_today >= settings.ai_max_requests_per_day:
        raise BudgetExceededError(
            f"Đã đạt giới hạn {settings.ai_max_requests_per_day} lần gọi AI trong ngày "
            "(AI_MAX_REQUESTS_PER_DAY).",
        )
    prices_set = (
        settings.ai_price_input_per_1m_tokens is not None
        and settings.ai_price_output_per_1m_tokens is not None
    )
    if (
        settings.ai_monthly_budget_usd > 0
        and prices_set
        and spent.month_cost_usd >= settings.ai_monthly_budget_usd
    ):
        raise BudgetExceededError(
            f"Đã dùng hết ngân sách AI tháng này ({settings.ai_monthly_budget_usd} USD).",
        )


_slots_lock = threading.Lock()
_slots: dict[int, threading.BoundedSemaphore] = {}


@contextmanager
def concurrency_slot(settings: Settings) -> Iterator[None]:
    """Process-wide cap on simultaneous provider calls (AI_MAX_CONCURRENT_REQUESTS)."""
    with _slots_lock:
        sem = _slots.setdefault(
            settings.ai_max_concurrent_requests,
            threading.BoundedSemaphore(settings.ai_max_concurrent_requests),
        )
    with sem:
        yield


class _HasUsage(Protocol):
    @property
    def usage(self) -> Usage: ...

    @property
    def model(self) -> str: ...


def guarded_call[R: _HasUsage](
    db: Session,
    settings: Settings,
    *,
    provider: str,
    model: str,
    question_id: uuid.UUID | None,
    fn: Callable[[], R],
) -> R:
    """Budget check → concurrency slot → bounded retries → usage log, for one provider call."""
    from app.explanations.interfaces import ProviderError
    from app.explanations.retry import call_with_retry

    def once() -> R:
        check_budget(db, settings)
        started = time.monotonic()
        try:
            with concurrency_slot(settings):
                result = fn()
        except ProviderError as exc:
            ms = int((time.monotonic() - started) * 1000)
            record(
                db, settings, provider=provider, model=model, question_id=question_id, ok=False,
                error_code=exc.code, usage=None, duration_ms=ms,
            )  # fmt: skip
            raise
        ms = int((time.monotonic() - started) * 1000)
        record(
            db, settings, provider=provider, model=result.model, question_id=question_id, ok=True,
            error_code=None, usage=result.usage, duration_ms=ms,
        )  # fmt: skip
        return result

    return call_with_retry(once, max_retries=settings.ai_max_retries)
