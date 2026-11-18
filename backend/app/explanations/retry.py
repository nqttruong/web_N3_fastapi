"""Bounded retries for transient provider errors: exponential backoff with full jitter.

Only errors with ``retryable=True`` (timeout, rate limit, connection/5xx) are retried.
Authentication, quota, bad request and validation errors are raised immediately.
"""

import random
import time
from collections.abc import Callable

from app.explanations.interfaces import ProviderError

BASE_DELAY = 1.0
MAX_DELAY = 30.0


def backoff_delay(attempt: int, rng: Callable[[], float] = random.random) -> float:
    return float(rng() * min(MAX_DELAY, BASE_DELAY * (2.0**attempt)))


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    max_retries: int,
    sleep: Callable[[float], None] | None = None,
    rng: Callable[[], float] | None = None,
    on_error: Callable[[ProviderError, int], None] | None = None,
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except ProviderError as exc:
            if on_error is not None:
                on_error(exc, attempt)
            if not exc.retryable or attempt >= max_retries:
                raise
            delay = (
                exc.retry_after
                if exc.retry_after is not None
                else backoff_delay(attempt, rng or random.random)
            )
            (sleep or time.sleep)(min(delay, MAX_DELAY))
            attempt += 1
