"""Detection data-access layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select

from app.enums import ViolationType
from app.models.detection import Detection
from app.repositories.base import BaseRepository
from app.utils.pagination import PageParams


class DetectionRepository(BaseRepository[Detection]):
    """Data access for :class:`Detection`."""

    model = Detection

    def _apply_filters(
        self,
        stmt: Select,
        camera_id: UUID | None,
        zone_id: UUID | None,
        violation_type: ViolationType | None,
        since: datetime | None,
        until: datetime | None,
    ) -> Select:
        if camera_id is not None:
            stmt = stmt.where(Detection.camera_id == camera_id)
        if zone_id is not None:
            stmt = stmt.where(Detection.zone_id == zone_id)
        if violation_type is not None:
            stmt = stmt.where(Detection.violation_type == violation_type)
        if since is not None:
            stmt = stmt.where(Detection.created_at >= since)
        if until is not None:
            stmt = stmt.where(Detection.created_at <= until)
        return stmt

    async def get_by_id(self, detection_id: UUID) -> Detection | None:
        result = await self.session.execute(
            select(Detection).where(Detection.detection_id == detection_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        params: PageParams,
        *,
        camera_id: UUID | None = None,
        zone_id: UUID | None = None,
        violation_type: ViolationType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[Detection], int]:
        base = self._apply_filters(
            select(Detection), camera_id, zone_id, violation_type, since, until
        )
        count_stmt = self._apply_filters(
            select(func.count()).select_from(Detection),
            camera_id,
            zone_id,
            violation_type,
            since,
            until,
        )
        total = int((await self.session.execute(count_stmt)).scalar_one())
        rows = await self.session.execute(
            base.order_by(Detection.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(rows.scalars().all()), total

    async def count_since(self, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Detection).where(Detection.created_at >= since)
        )
        return int(result.scalar_one())
