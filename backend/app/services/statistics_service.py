"""Detection statistics / analytics business logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ViolationType, ZoneSeverity
from app.repositories.alert_repo import AlertRepository
from app.repositories.camera_repo import CameraRepository
from app.repositories.detection_repo import DetectionRepository
from app.repositories.statistics_repo import StatisticsRepository
from app.repositories.zone_repo import ZoneRepository
from app.schemas.statistics import (
    CameraCount,
    CountByKey,
    DetectionStatistics,
    StatisticsSummary,
    TimeBucket,
    ZoneCount,
)

_TYPE_LABELS = {
    ViolationType.HELMET_VIOLATION.value: "Helmet Violation",
    ViolationType.LINE_CROSSING.value: "Line Crossing",
}
_SEVERITY_LABELS = {
    ZoneSeverity.LEVEL_1.value: "Level 1",
    ZoneSeverity.LEVEL_2.value: "Level 2",
    ZoneSeverity.DANGER.value: "Danger",
}


class StatisticsService:
    """Aggregates detections into KPIs and chart-ready series."""

    def __init__(self, session: AsyncSession) -> None:
        self._stats = StatisticsRepository(session)
        self._detections = DetectionRepository(session)
        self._alerts = AlertRepository(session)
        self._cameras = CameraRepository(session)
        self._zones = ZoneRepository(session)

    async def get_statistics(self, window_hours: int = 24) -> DetectionStatistics:
        now = datetime.now(UTC)
        since = now - timedelta(hours=window_hours)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        summary = StatisticsSummary(
            total_detections=await self._detections.count(),
            total_alerts=await self._alerts.count(),
            unacknowledged_alerts=await self._alerts.count_unacknowledged(),
            active_cameras=await self._cameras.count_active(),
            total_cameras=await self._cameras.count(),
            total_zones=await self._zones.count(),
            detections_today=await self._detections.count_since(start_of_day),
        )

        by_type_raw = await self._stats.count_by_violation_type(since)
        by_type = [
            CountByKey(key=k, label=_TYPE_LABELS.get(k, k), count=v) for k, v in by_type_raw.items()
        ]

        by_sev_raw = await self._stats.count_by_severity(since)
        by_severity = [
            CountByKey(key=k, label=_SEVERITY_LABELS.get(k, k), count=v)
            for k, v in by_sev_raw.items()
        ]

        by_camera = [
            CameraCount(camera_id=cid, camera_name=name, count=count)
            for cid, name, count in await self._stats.count_by_camera(since)
        ]
        by_zone = [
            ZoneCount(zone_id=zid, zone_name=name, count=count)
            for zid, name, count in await self._stats.count_by_zone(since)
        ]

        bucket_hours = 1 if window_hours <= 48 else 24
        over_time = [
            TimeBucket(bucket=bucket, count=count)
            for bucket, count in await self._stats.counts_over_time(since, bucket_hours)
        ]

        return DetectionStatistics(
            summary=summary,
            by_type=by_type,
            by_severity=by_severity,
            by_camera=by_camera,
            by_zone=by_zone,
            over_time=over_time,
        )
