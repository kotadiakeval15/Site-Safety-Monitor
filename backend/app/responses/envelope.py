"""A single response envelope applied to every API response.

Shape::

    {
      "success": bool,
      "message": str,
      "data": <T> | null,
      "error": {code, details} | null,
      "meta": {timestamp, request_id, pagination?}
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.request_context import get_request_id

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination details attached to list responses."""

    page: int
    page_size: int
    total_items: int
    total_pages: int


class Meta(BaseModel):
    """Metadata attached to every response."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = Field(default_factory=get_request_id)
    pagination: PaginationMeta | None = None


class ErrorDetail(BaseModel):
    """Structured error information."""

    code: str
    details: Any | None = None


class Envelope(BaseModel, Generic[T]):
    """Uniform response body."""

    success: bool
    message: str
    data: T | None = None
    error: ErrorDetail | None = None
    meta: Meta = Field(default_factory=Meta)


def success_response(
    data: Any = None,
    message: str = "OK",
    pagination: PaginationMeta | None = None,
) -> dict[str, Any]:
    """Build a serialized success envelope."""

    return Envelope[Any](
        success=True,
        message=message,
        data=data,
        error=None,
        meta=Meta(pagination=pagination),
    ).model_dump(mode="json")


def paginated_response(
    items: Any,
    *,
    page: int,
    page_size: int,
    total_items: int,
    total_pages: int,
    message: str = "OK",
) -> dict[str, Any]:
    """Build a success envelope carrying pagination metadata."""

    return success_response(
        data=items,
        message=message,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


def error_response(
    message: str,
    code: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build a serialized error envelope."""

    return Envelope[Any](
        success=False,
        message=message,
        data=None,
        error=ErrorDetail(code=code, details=details),
        meta=Meta(),
    ).model_dump(mode="json")
