"""Reusable Pydantic building blocks."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AnyHttpUrl, BaseModel, ConfigDict, StringConstraints


def _http_url(value: str) -> str:
    url = AnyHttpUrl(value)
    if url.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")
    return str(url)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset (e.g. 2026-01-01T00:00:00Z)")
    return value.astimezone(UTC)


# Trimmed, non-empty text. Japanese text is stored exactly as given (no NFKC normalisation).
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
HttpUrlStr = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2048), AfterValidator(_http_url)
]
AwareDatetime = Annotated[datetime, AfterValidator(_aware)]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


__all__ = ["APIModel", "AwareDatetime", "HttpUrlStr", "NonBlankStr"]
