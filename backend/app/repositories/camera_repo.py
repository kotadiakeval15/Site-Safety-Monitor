"""Camera data-access layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.enums import CameraStatus
from app.models.camera import Camera
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    """Data access for :class:`Camera`."""

    model = Camera

    async def get_by_id(self, camera_id: UUID) -> Camera | None:
        result = await self.session.execute(
            select(Camera).options(selectinload(Camera.zones)).where(Camera.camera_id == camera_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Camera]:
        result = await self.session.execute(
            select(Camera).options(selectinload(Camera.zones)).order_by(Camera.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Camera]:
        result = await self.session.execute(
            select(Camera)
            .options(selectinload(Camera.zones))
            .where(Camera.status == CameraStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Camera).where(Camera.status == CameraStatus.ACTIVE)
        )
        return int(result.scalar_one())
