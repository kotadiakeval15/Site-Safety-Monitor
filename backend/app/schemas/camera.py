"""Camera DTOs (Create / Update / Read)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.enums import CameraStatus, DetectionMode, SourceType
from app.schemas.common import ORMModel
from app.schemas.zone import ZoneRead


class CameraCreate(BaseModel):
    """Payload to register a new camera."""

    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    stream_url: str = Field(min_length=1, max_length=2048)
    detection_mode: DetectionMode = DetectionMode.RESTRICTED_AREA


class CameraUpdate(BaseModel):
    """Partial update payload for a camera."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: SourceType | None = None
    stream_url: str | None = Field(default=None, min_length=1, max_length=2048)
    detection_mode: DetectionMode | None = None


class CameraRead(ORMModel):
    """Camera read DTO."""

    camera_id: uuid.UUID
    name: str
    source_type: SourceType
    stream_url: str
    status: CameraStatus
    detection_mode: DetectionMode
    has_video: bool = False


class CameraDetailRead(CameraRead):
    """Camera read DTO including its bound zones."""

    zones: list[ZoneRead] = Field(default_factory=list)
