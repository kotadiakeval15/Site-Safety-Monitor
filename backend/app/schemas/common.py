"""Shared schema primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Base for read DTOs mapped from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class PaginationQuery(BaseModel):
    """Common pagination query parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MessageResponse(BaseModel):
    """Simple message payload."""

    message: str
