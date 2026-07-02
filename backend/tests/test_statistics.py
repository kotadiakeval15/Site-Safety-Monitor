"""Detection statistics endpoint tests."""

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


async def _ingest(camera_id: str, violation_type: str, severity: str) -> None:
    async with AsyncSessionLocal() as session:
        await DetectionService(session).ingest_worker_event(
            DetectionMessage(
                camera_id=camera_id,
                worker_id=1,
                violation_type=violation_type,
                severity=severity,
                message="test",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_statistics_aggregates(client, token_for):
    admin = token_for("admin")
    camera_id = await _create_camera(client, admin)
    await _ingest(camera_id, "helmet_violation", "danger")
    await _ingest(camera_id, "line_crossing", "level_2")
    await _ingest(camera_id, "line_crossing", "level_1")

    resp = await client.get("/api/v1/statistics", headers=token_for("viewer"))
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["summary"]["total_detections"] == 3
    assert data["summary"]["total_alerts"] == 3
    assert data["summary"]["total_cameras"] == 1

    by_type = {row["key"]: row["count"] for row in data["by_type"]}
    assert by_type["line_crossing"] == 2
    assert by_type["helmet_violation"] == 1

    by_camera = {row["camera_name"]: row["count"] for row in data["by_camera"]}
    assert by_camera["Cam"] == 3
