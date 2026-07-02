"""Detection ingestion and retrieval business logic."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.enums import AlertLevel, CrossedLine, ViolationType, ZoneSeverity
from app.exceptions.base import NotFoundError
from app.models.alert import Alert
from app.models.detection import Detection
from app.repositories.alert_repo import AlertRepository
from app.repositories.detection_repo import DetectionRepository
from app.schemas.detection import AlertAckRequest, AlertRead, DetectionRead
from app.utils.datetime import utcnow
from app.utils.images import save_screenshot
from app.utils.pagination import Page, PageParams, paginate
from app.workers.messages import DetectionMessage

logger = get_logger(__name__)


class DetectionService:
    """Persist worker detections and expose the detection/alert feeds."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._detections = DetectionRepository(session)
        self._alerts = AlertRepository(session)

    async def ingest_worker_event(self, message: DetectionMessage) -> dict[str, Any] | None:
        """Persist a worker detection + its alert and return a WS payload."""

        settings = get_settings()
        screenshot_path = save_screenshot(
            settings.screenshots_dir,
            message.camera_id,
            message.worker_id,
            message.screenshot_base64,
        )
        detection = Detection(
            camera_id=UUID(message.camera_id),
            zone_id=UUID(message.zone_id) if message.zone_id else None,
            worker_id=message.worker_id,
            violation_type=ViolationType(message.violation_type),
            severity=ZoneSeverity(message.severity),
            crossed_line=CrossedLine(message.crossed_line) if message.crossed_line else None,
            confidence=message.confidence,
            bbox=message.bbox,
            foot_x=message.foot_x,
            foot_y=message.foot_y,
            screenshot_path=screenshot_path,
            message=message.message,
        )
        await self._detections.add(detection)

        alert = Alert(
            detection_id=detection.detection_id,
            level=AlertLevel(message.severity),
            message=message.message,
            acknowledged=False,
        )
        await self._alerts.add(alert)

        logger.info(
            "Ingested %s detection for camera %s worker %s",
            message.violation_type,
            message.camera_id,
            message.worker_id,
        )
        return {
            "type": "alert",
            "alert_id": str(alert.alert_id),
            "detection_id": str(detection.detection_id),
            "camera_id": message.camera_id,
            "worker_id": message.worker_id,
            "violation_type": message.violation_type,
            "severity": message.severity,
            "level": alert.level.value,
            "crossed_line": message.crossed_line,
            "message": message.message,
            "screenshot_path": screenshot_path,
            "timestamp": detection.created_at.isoformat(),
        }

    async def list_detections(
        self,
        params: PageParams,
        *,
        camera_id: UUID | None = None,
        zone_id: UUID | None = None,
        violation_type: ViolationType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Page[DetectionRead]:
        rows, total = await self._detections.list_paginated(
            params,
            camera_id=camera_id,
            zone_id=zone_id,
            violation_type=violation_type,
            since=since,
            until=until,
        )
        items = [DetectionRead.model_validate(r) for r in rows]
        return paginate(items, total, params)

    async def list_alerts(
        self, params: PageParams, *, unacknowledged_only: bool = False
    ) -> Page[AlertRead]:
        rows, total = await self._alerts.list_paginated(
            params, unacknowledged_only=unacknowledged_only
        )
        items = [AlertRead.model_validate(r) for r in rows]
        return paginate(items, total, params)

    async def acknowledge_alert(
        self, alert_id: UUID, payload: AlertAckRequest, actor_id: UUID
    ) -> AlertRead:
        alert = await self._alerts.get_by_id(alert_id)
        if alert is None:
            raise NotFoundError("Alert not found")
        alert.acknowledged = payload.acknowledged
        alert.acked_by = actor_id if payload.acknowledged else None
        alert.acked_at = utcnow() if payload.acknowledged else None
        await self._session.flush()
        result = AlertRead.model_validate(alert)
        if payload.acknowledged:
            from app.realtime.websocket_manager import alert_ws_manager

            await alert_ws_manager.broadcast(
                {
                    "type": "alert_acknowledged",
                    "alert_id": str(alert_id),
                    "acknowledged": True,
                }
            )
        return result
