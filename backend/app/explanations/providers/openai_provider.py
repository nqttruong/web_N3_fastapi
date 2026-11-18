"""OpenAI Responses API + Structured Outputs (``client.responses.parse(text_format=...)``).

* ``store=False``: requests are not stored for later retrieval by OpenAI's Responses store.
* SDK retries are disabled (``max_retries=0``); retries are done by ``retry.py`` so they are
  bounded, logged and respect ``Retry-After``.
* The API key is read from settings only; it is never logged or returned.
"""

from typing import Any

import openai
from pydantic import ValidationError

from app.core.config import Settings
from app.explanations import prompts
from app.explanations.context import QuestionContext
from app.explanations.interfaces import (
    BadOutputError,
    GenerationResult,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    Usage,
)
from app.explanations.payload import ExplanationPayload


def _retry_after(exc: openai.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def map_openai_error(exc: Exception) -> ProviderError:
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return ProviderAuthError(type(exc).__name__)
    if isinstance(exc, openai.RateLimitError):
        body: Any = exc.body if isinstance(exc.body, dict) else {}
        if "insufficient_quota" in str(body.get("code", "")) + str(exc):
            return ProviderQuotaError("insufficient_quota")
        return ProviderRateLimitError("rate_limited", retry_after=_retry_after(exc))
    if isinstance(exc, openai.APITimeoutError):
        return ProviderTimeoutError("timeout")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderUnavailableError("connection")
    if isinstance(exc, openai.InternalServerError):
        return ProviderUnavailableError(f"http {exc.status_code}")
    if isinstance(
        exc, openai.BadRequestError | openai.NotFoundError | openai.UnprocessableEntityError
    ):
        return ProviderBadRequestError(f"http {exc.status_code}")
    if isinstance(exc, openai.LengthFinishReasonError | openai.ContentFilterFinishReasonError):
        return BadOutputError(type(exc).__name__)
    if isinstance(exc, ValidationError):
        return BadOutputError("schema")
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            return ProviderUnavailableError(f"http {exc.status_code}")
        return ProviderBadRequestError(f"http {exc.status_code}")
    return ProviderError(type(exc).__name__)


class OpenAIStructuredClient:
    """Shared Responses API + Structured Outputs call, reused by every AI feature
    (explanations in PR3, practice generation in PR4)."""

    provider = "openai"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.model = settings.openai_model
        self.max_output_tokens = settings.ai_max_output_tokens
        if client is None:
            assert settings.openai_api_key is not None
            client = openai.OpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.ai_request_timeout,
                max_retries=0,
            )
        self.client = client

    def parse[M](
        self, *, instructions: str, input: str, text_format: type[M], cache_key: str
    ) -> tuple[M, Usage, str]:
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=input,
                text_format=text_format,
                max_output_tokens=self.max_output_tokens,
                store=False,
                prompt_cache_key=cache_key,
            )
        except Exception as exc:
            raise map_openai_error(exc) from exc
        for item in getattr(response, "output", None) or []:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    raise BadOutputError("refusal")
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, text_format):
            raise BadOutputError("no_parsed_output")
        usage = getattr(response, "usage", None)
        return (
            parsed,
            Usage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            ),
            str(getattr(response, "model", None) or self.model),
        )


class OpenAIExplanationGenerator:
    provider = "openai"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.structured = OpenAIStructuredClient(settings, client)
        self.model = self.structured.model

    def generate(
        self, ctx: QuestionContext, *, feedback: list[str] | None = None
    ) -> GenerationResult:
        prompt = prompts.render(ctx, feedback=feedback)
        payload, usage, model = self.structured.parse(
            instructions=prompt.instructions,
            input=prompt.input,
            text_format=ExplanationPayload,
            cache_key=prompt.version,
        )
        return GenerationResult(payload=payload, usage=usage, model=model)
