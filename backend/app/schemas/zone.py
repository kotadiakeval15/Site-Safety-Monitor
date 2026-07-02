"""Zone DTOs (Create / Update / Read)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.enums import ZoneSeverity
from app.schemas.common import ORMModel

_COORD = Field(default=None, ge=0.0, le=1.0)


class ZoneBase(BaseModel):
    """Fields shared by create/update."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    severity: ZoneSeverity
    line_y: float = Field(ge=0.0, le=1.0, description="Line position as fraction of frame height")
    # Optional oriented segment endpoints (normalized 0..1). Absent = horizontal.
    line_x1: float | None = _COORD
    line_y1: float | None = _COORD
    line_x2: float | None = _COORD
    line_y2: float | None = _COORD
    is_active: bool = True


class ZoneCreate(ZoneBase):
    """Payload to create a zone bound to a camera."""

    camera_id: uuid.UUID


class ZoneUpdate(BaseModel):
    """Partial update payload."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    severity: ZoneSeverity | None = None
    line_y: float | None = Field(default=None, ge=0.0, le=1.0)
    line_x1: float | None = _COORD
    line_y1: float | None = _COORD
    line_x2: float | None = _COORD
    line_y2: float | None = _COORD
    is_active: bool | None = None


class ZoneRead(ORMModel):
    """Zone read DTO."""

    zone_id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    description: str | None
    severity: ZoneSeverity
    line_y: float
    line_x1: float | None
    line_y1: float | None
    line_x2: float | None
    line_y2: float | None
    is_active: bool
