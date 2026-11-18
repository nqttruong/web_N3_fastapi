"""Consistent success envelopes.

* Single resource: ``{"data": {...}}``
* Collection:      ``{"data": [...], "meta": {"page", "page_size", "total", "total_pages"}}``
"""

import math
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page")] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, params: PageParams, total: int) -> "PageMeta":
        return cls(
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=math.ceil(total / params.page_size) if total else 0,
        )


class DataResponse[T](BaseModel):
    data: T


class PageResponse[T](BaseModel):
    data: list[T]
    meta: PageMeta


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(title="ErrorResponse")
    error: ErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Conflict / duplicate"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
