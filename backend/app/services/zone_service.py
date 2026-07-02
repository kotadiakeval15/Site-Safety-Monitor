"""Zone CRUD business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import NotFoundError
from app.models.zone import Zone
from app.repositories.audit_repo import AuditRepository
from app.repositories.camera_repo import CameraRepository
from app.repositories.zone_repo import ZoneRepository
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneUpdate


class ZoneService:
    """CRUD operations for safety zones."""

    def __init__(self, session: AsyncSession) -> None:
        self._zones = ZoneRepository(session)
        self._cameras = CameraRepository(session)
        self._audit = AuditRepository(session)

    async def list_zones(self) -> list[ZoneRead]:
        zones = await self._zones.list_all()
        return [ZoneRead.model_validate(z) for z in zones]

    async def list_for_camera(self, camera_id: UUID) -> list[ZoneRead]:
        zones = await self._zones.list_for_camera(camera_id)
        return [ZoneRead.model_validate(z) for z in zones]

    async def get_zone(self, zone_id: UUID) -> ZoneRead:
        zone = await self._require(zone_id)
        return ZoneRead.model_validate(zone)

    async def create_zone(self, payload: ZoneCreate, actor_id: UUID) -> ZoneRead:
        camera = await self._cameras.get_by_id(payload.camera_id)
        if camera is None:
            raise NotFoundError("Camera not found")
        zone = Zone(
            name=payload.name,
            description=payload.description,
            camera_id=payload.camera_id,
            severity=payload.severity,
            line_y=payload.line_y,
            line_x1=payload.line_x1,
            line_y1=payload.line_y1,
            line_x2=payload.line_x2,
            line_y2=payload.line_y2,
            is_active=payload.is_active,
        )
        await self._zones.add(zone)
        await self._audit.record("zone.create", actor_id, {"zone_id": str(zone.zone_id)})
        return ZoneRead.model_validate(zone)

    async def update_zone(self, zone_id: UUID, payload: ZoneUpdate, actor_id: UUID) -> ZoneRead:
        zone = await self._require(zone_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(zone, field, value)
        await self._zones.session.flush()
        await self._audit.record("zone.update", actor_id, {"zone_id": str(zone_id), **data})
        return ZoneRead.model_validate(zone)

    async def delete_zone(self, zone_id: UUID, actor_id: UUID) -> None:
        zone = await self._require(zone_id)
        await self._zones.delete(zone)
        await self._audit.record("zone.delete", actor_id, {"zone_id": str(zone_id)})

    async def _require(self, zone_id: UUID) -> Zone:
        zone = await self._zones.get_by_id(zone_id)
        if zone is None:
            raise NotFoundError("Zone not found")
        return zone
