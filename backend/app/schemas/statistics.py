"""Detection statistics DTOs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CountByKey(BaseModel):
    """Generic labelled count bucket."""

    key: str
    label: str
    count: int


class CameraCount(BaseModel):
    """Violation count for a single camera."""

    camera_id: uuid.UUID
    camera_name: str
    count: int


class ZoneCount(BaseModel):
    """Violation count for a single zone."""

    zone_id: uuid.UUID | None
    zone_name: str
    count: int


class TimeBucket(BaseModel):
    """Violation count within a time bucket."""

    bucket: datetime
    count: int


class StatisticsSummary(BaseModel):
    """Aggregated KPIs for the statistics dashboard."""

    total_detections: int
    total_alerts: int
    unacknowledged_alerts: int
    active_cameras: int
    total_cameras: int
    total_zones: int
    detections_today: int


class DetectionStatistics(BaseModel):
    """Full statistics payload."""

    summary: StatisticsSummary
    by_type: list[CountByKey]
    by_severity: list[CountByKey]
    by_camera: list[CameraCount]
    by_zone: list[ZoneCount]
    over_time: list[TimeBucket]
