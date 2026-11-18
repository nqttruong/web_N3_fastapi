"""Provider contract for explanation generation (implemented in PR3).

A generator turns one ``QuestionContext`` into a parsed ``ExplanationPayload``. It does not
touch the database, does not validate business rules (``validation.py`` does) and raises the
typed errors below so callers can decide what to retry.
"""

from dataclasses import dataclass
from typing import Protocol

from app.explanations.context import QuestionContext
from app.explanations.payload import ExplanationPayload


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class GenerationResult:
    payload: ExplanationPayload
    usage: Usage
    model: str  # model actually reported by the provider


class ProviderError(Exception):
    """Base class. ``retryable`` tells the retry loop whether trying again can help."""

    code = "provider_error"
    retryable = False
    user_message = "Nhà cung cấp AI trả lỗi."

    def __init__(self, detail: str = "", *, retry_after: float | None = None) -> None:
        super().__init__(detail or self.user_message)
        self.detail = detail
        self.retry_after = retry_after


class ProviderAuthError(ProviderError):
    code = "provider_auth"
    user_message = (
        "API key không hợp lệ hoặc không có quyền dùng model. Kiểm tra OPENAI_API_KEY/OPENAI_MODEL."
    )


class ProviderQuotaError(ProviderError):
    code = "provider_quota"
    user_message = "Tài khoản AI đã hết hạn mức/quota."


class ProviderBadRequestError(ProviderError):
    code = "provider_bad_request"
    user_message = "Yêu cầu bị nhà cung cấp từ chối (model không hỗ trợ hoặc tham số sai)."


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limited"
    retryable = True
    user_message = "Nhà cung cấp AI đang giới hạn tốc độ. Hãy thử lại sau."


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    retryable = True
    user_message = "Gọi AI quá thời gian chờ."


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"
    retryable = True
    user_message = "Không kết nối được tới nhà cung cấp AI."


class BadOutputError(ProviderError):
    """Output missing, refused, truncated or not matching the schema (format retry)."""

    code = "bad_output"
    user_message = "AI trả kết quả không đúng định dạng."


class ExplanationGenerator(Protocol):
    provider: str
    model: str

    def generate(
        self, ctx: QuestionContext, *, feedback: list[str] | None = None
    ) -> GenerationResult: ...
