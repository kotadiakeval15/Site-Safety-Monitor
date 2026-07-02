"""Detection ingestion + retrieval + alert acknowledgement tests."""

from __future__ import annotations

import pytest
from app.core.database import AsyncSessionLocal
from app.services.detection_service import DetectionService
from app.workers.messages import DetectionMessage


async def _create_camera(client, headers) -> str:
    resp = await client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "Cam", "source_type": "file", "stream_url": "/data/x.mp4"},
    )
    return resp.json()["data"]["camera_id"]


async def _ingest(camera_id: str, **overrides) -> None:
    message = DetectionMessage(
        camera_id=camera_id,
        worker_id=overrides.get("worker_id", 1),
        violation_type=overrides.get("violation_type", "helmet_violation"),
        severity=overrides.get("severity", "danger"),
        crossed_line=overrides.get("crossed_line"),
        confidence=overrides.get("confidence", 0.9),
        message=overrides.get("message", "Helmet violation - Worker 1"),
    )
    async with AsyncSessionLocal() as session:
        await DetectionService(session).ingest_worker_event(message)
        await session.commit()


@pytest.mark.asyncio
async def test_detection_feed_and_alert_ack(client, token_for):
    admin = token_for("admin")
    camera_id = await _create_camera(client, admin)

    await _ingest(camera_id)
    await _ingest(
        camera_id,
        worker_id=2,
        violation_type="line_crossing",
        severity="level_2",
        crossed_line="yellow",
    )

    detections = await client.get("/api/v1/detections", headers=token_for("viewer"))
    assert detections.status_code == 200
    body = detections.json()
    assert body["meta"]["pagination"]["total_items"] == 2
    assert len(body["data"]) == 2

    filtered = await client.get(
        "/api/v1/detections",
        headers=admin,
        params={"violation_type": "line_crossing"},
    )
    assert filtered.json()["meta"]["pagination"]["total_items"] == 1

    alerts = await client.get("/api/v1/alerts", headers=admin)
    alert_id = alerts.json()["data"][0]["alert_id"]

    ack = await client.put(f"/api/v1/alerts/{alert_id}", headers=admin, json={"acknowledged": True})
    assert ack.status_code == 200
    assert ack.json()["data"]["acknowledged"] is True


@pytest.mark.asyncio
async def test_viewer_cannot_ack_alert(client, token_for):
    admin = token_for("admin")
    camera_id = await _create_camera(client, admin)
    await _ingest(camera_id)
    alerts = await client.get("/api/v1/alerts", headers=admin)
    alert_id = alerts.json()["data"][0]["alert_id"]

    resp = await client.put(
        f"/api/v1/alerts/{alert_id}", headers=token_for("viewer"), json={"acknowledged": True}
    )
    assert resp.status_code == 403
