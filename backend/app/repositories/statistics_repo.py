"""Aggregation queries powering the Detection Statistics feature."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.models.detection import Detection
from app.models.zone import Zone


class StatisticsRepository:
    """Read-only aggregation queries over detections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_by_violation_type(self, since: datetime | None = None) -> dict[str, int]:
        stmt = select(Detection.violation_type, func.count()).group_by(Detection.violation_type)
        if since is not None:
            stmt = stmt.where(Detection.created_at >= since)
        result = await self._session.execute(stmt)
        return {str(row[0]): int(row[1]) for row in result.all()}

    async def count_by_severity(self, since: datetime | None = None) -> dict[str, int]:
        stmt = select(Detection.severity, func.count()).group_by(Detection.severity)
        if since is not None:
            stmt = stmt.where(Detection.created_at >= since)
        result = await self._session.execute(stmt)
        return {str(row[0]): int(row[1]) for row in result.all()}

    async def count_by_camera(self, since: datetime | None = None) -> list[tuple[str, str, int]]:
        stmt = (
            select(Camera.camera_id, Camera.name, func.count(Detection.detection_id))
            .select_from(Camera)
            .join(Detection, Detection.camera_id == Camera.camera_id, isouter=True)
            .group_by(Camera.camera_id, Camera.name)
        )
        if since is not None:
            stmt = stmt.where(Detection.created_at >= since)
        result = await self._session.execute(stmt)
        return [(str(r[0]), r[1], int(r[2])) for r in result.all()]

    async def count_by_zone(
        self, since: datetime | None = None
    ) -> list[tuple[str | None, str, int]]:
        stmt = (
            select(Zone.zone_id, Zone.name, func.count(Detection.detection_id))
            .select_from(Detection)
            .join(Zone, Detection.zone_id == Zone.zone_id, isouter=True)
            .group_by(Zone.zone_id, Zone.name)
        )
        if since is not None:
            stmt = stmt.where(Detection.created_at >= since)
        result = await self._session.execute(stmt)
        return [
            (str(r[0]) if r[0] is not None else None, r[1] or "Unassigned", int(r[2]))
            for r in result.all()
        ]

    async def counts_over_time(
        self, since: datetime, bucket_hours: int = 1
    ) -> list[tuple[datetime, int]]:
        """Bucket detections into fixed windows.

        Bucketing is done in Python to remain portable across PostgreSQL and the
        SQLite test database (which lacks ``date_trunc``).
        """

        result = await self._session.execute(
            select(Detection.created_at).where(Detection.created_at >= since)
        )
        span = timedelta(hours=bucket_hours)
        buckets: dict[datetime, int] = defaultdict(int)
        for (created_at,) in result.all():
            ts = created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            elapsed = ts - since
            index = int(elapsed.total_seconds() // span.total_seconds())
            bucket_start = since + span * index
            buckets[bucket_start] += 1
        return sorted(buckets.items())
