"""Zone CRUD controller."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_admin, require_viewer
from app.models.user import User
from app.responses import success_response
from app.schemas.zone import ZoneCreate, ZoneUpdate
from app.services.zone_service import ZoneService

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("")
async def list_zones(session: DbSession, _user: User = Depends(require_viewer)) -> dict:
    zones = await ZoneService(session).list_zones()
    return success_response([z.model_dump(mode="json") for z in zones])


@router.get("/{zone_id}")
async def get_zone(
    zone_id: UUID, session: DbSession, _user: User = Depends(require_viewer)
) -> dict:
    zone = await ZoneService(session).get_zone(zone_id)
    return success_response(zone.model_dump(mode="json"))


@router.post("", status_code=201)
async def create_zone(
    payload: ZoneCreate, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    zone = await ZoneService(session).create_zone(payload, admin.user_id)
    return success_response(zone.model_dump(mode="json"), message="Zone created")


@router.put("/{zone_id}")
async def update_zone(
    zone_id: UUID,
    payload: ZoneUpdate,
    session: DbSession,
    admin: User = Depends(require_admin),
) -> dict:
    zone = await ZoneService(session).update_zone(zone_id, payload, admin.user_id)
    return success_response(zone.model_dump(mode="json"), message="Zone updated")


@router.delete("/{zone_id}")
async def delete_zone(
    zone_id: UUID, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    await ZoneService(session).delete_zone(zone_id, admin.user_id)
    return success_response(message="Zone deleted")
