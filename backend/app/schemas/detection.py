"""Detection and alert DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import AlertLevel, CrossedLine, ViolationType, ZoneSeverity
from app.schemas.common import ORMModel


class DetectionRead(ORMModel):
    """Detection read DTO."""

    detection_id: uuid.UUID
    camera_id: uuid.UUID
    zone_id: uuid.UUID | None
    worker_id: int
    violation_type: ViolationType
    severity: ZoneSeverity
    crossed_line: CrossedLine | None
    confidence: float
    bbox: list[int] | None
    foot_x: float | None
    foot_y: float | None
    screenshot_path: str | None
    message: str | None
    created_at: datetime


class AlertRead(ORMModel):
    """Alert read DTO."""

    alert_id: uuid.UUID
    detection_id: uuid.UUID
    level: AlertLevel
    message: str | None
    acknowledged: bool
    acked_by: uuid.UUID | None
    acked_at: datetime | None
    created_at: datetime


class AlertAckRequest(BaseModel):
    """Acknowledge/unacknowledge an alert."""

    acknowledged: bool = True


class WorkerEventIngest(BaseModel):
    """Detection event emitted by a camera worker process (internal IPC)."""

    camera_id: uuid.UUID
    worker_id: int
    violation_type: ViolationType
    severity: ZoneSeverity
    crossed_line: CrossedLine | None = None
    confidence: float = 0.0
    bbox: list[int] | None = None
    foot_x: float | None = None
    foot_y: float | None = None
    screenshot_base64: str | None = None
    message: str | None = None
    zone_id: uuid.UUID | None = None


class DetectionFilter(BaseModel):
    """Optional filters for the detection feed."""

    camera_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    violation_type: ViolationType | None = None
    since: datetime | None = None
    until: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
