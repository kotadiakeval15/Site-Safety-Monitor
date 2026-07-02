"""Zone data-access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.models.zone import Zone
from app.repositories.base import BaseRepository


class ZoneRepository(BaseRepository[Zone]):
    """Data access for :class:`Zone`."""

    model = Zone

    async def get_by_id(self, zone_id: UUID) -> Zone | None:
        result = await self.session.execute(select(Zone).where(Zone.zone_id == zone_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Zone]:
        result = await self.session.execute(select(Zone).order_by(Zone.created_at.desc()))
        return list(result.scalars().all())

    async def list_for_camera(self, camera_id: UUID, active_only: bool = False) -> list[Zone]:
        stmt = select(Zone).where(Zone.camera_id == camera_id)
        if active_only:
            stmt = stmt.where(Zone.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(Zone.severity))
        return list(result.scalars().all())
