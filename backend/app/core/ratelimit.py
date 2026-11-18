"""Tiny in-process rate limiter for expensive endpoints (imports/OCR).

Single-process local app: an in-memory sliding window per client is enough. Behind a proxy
or with several workers this must move to a shared store (documented in import-security.md).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request, status

from app.core.config import get_settings
from app.core.errors import AppError


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitError(
                    "Quá nhiều yêu cầu nhập đề. Vui lòng thử lại sau ít phút.",
                    details={"limit_per_minute": limit},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


import_limiter = SlidingWindowLimiter()


def import_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    import_limiter.check(client, get_settings().import_rate_limit_per_minute)
