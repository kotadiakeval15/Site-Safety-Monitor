"""Alert data-access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.enums import AlertLevel
from app.models.alert import Alert
from app.repositories.base import BaseRepository
from app.utils.pagination import PageParams


class AlertRepository(BaseRepository[Alert]):
    """Data access for :class:`Alert`."""

    model = Alert

    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        result = await self.session.execute(select(Alert).where(Alert.alert_id == alert_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self, params: PageParams, *, unacknowledged_only: bool = False
    ) -> tuple[list[Alert], int]:
        base = select(Alert)
        count_stmt = select(func.count()).select_from(Alert)
        if unacknowledged_only:
            base = base.where(Alert.acknowledged.is_(False))
            count_stmt = count_stmt.where(Alert.acknowledged.is_(False))
        total = int((await self.session.execute(count_stmt)).scalar_one())
        rows = await self.session.execute(
            base.order_by(Alert.created_at.desc()).offset(params.offset).limit(params.limit)
        )
        return list(rows.scalars().all()), total

    async def count_unacknowledged(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Alert).where(Alert.acknowledged.is_(False))
        )
        return int(result.scalar_one())

    async def count_active_danger(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Alert)
            .where(Alert.level == AlertLevel.DANGER, Alert.acknowledged.is_(False))
        )
        return int(result.scalar_one())
