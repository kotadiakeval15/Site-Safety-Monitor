"""Detection feed and alert controller."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, PaginationDep, require_admin, require_viewer
from app.enums import ViolationType
from app.models.user import User
from app.responses import paginated_response, success_response
from app.schemas.detection import AlertAckRequest
from app.services.detection_service import DetectionService

router = APIRouter(tags=["detections"])


@router.get("/detections")
async def list_detections(
    session: DbSession,
    pagination: PaginationDep,
    _user: User = Depends(require_viewer),
    camera_id: UUID | None = Query(default=None),
    zone_id: UUID | None = Query(default=None),
    violation_type: ViolationType | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
) -> dict:
    page = await DetectionService(session).list_detections(
        pagination,
        camera_id=camera_id,
        zone_id=zone_id,
        violation_type=violation_type,
        since=since,
        until=until,
    )
    return paginated_response(
        [d.model_dump(mode="json") for d in page.items],
        page=page.page,
        page_size=page.page_size,
        total_items=page.total_items,
        total_pages=page.total_pages,
    )


@router.get("/alerts")
async def list_alerts(
    session: DbSession,
    pagination: PaginationDep,
    _user: User = Depends(require_viewer),
    unacknowledged_only: bool = Query(default=False),
) -> dict:
    page = await DetectionService(session).list_alerts(
        pagination, unacknowledged_only=unacknowledged_only
    )
    return paginated_response(
        [a.model_dump(mode="json") for a in page.items],
        page=page.page,
        page_size=page.page_size,
        total_items=page.total_items,
        total_pages=page.total_pages,
    )


@router.put("/alerts/{alert_id}")
async def acknowledge_alert(
    alert_id: UUID,
    payload: AlertAckRequest,
    session: DbSession,
    admin: User = Depends(require_admin),
) -> dict:
    alert = await DetectionService(session).acknowledge_alert(alert_id, payload, admin.user_id)
    return success_response(alert.model_dump(mode="json"), message="Alert updated")
