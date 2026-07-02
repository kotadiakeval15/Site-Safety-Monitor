"""Zone CRUD tests."""

from __future__ import annotations

import pytest


async def _camera(client, headers) -> str:
    resp = await client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "Cam", "source_type": "file", "stream_url": "/data/x.mp4"},
    )
    return resp.json()["data"]["camera_id"]


@pytest.mark.asyncio
async def test_zone_crud_flow(client, token_for):
    admin = token_for("admin")
    camera_id = await _camera(client, admin)

    create = await client.post(
        "/api/v1/zones",
        headers=admin,
        json={
            "name": "Red Line",
            "camera_id": camera_id,
            "severity": "danger",
            "line_y": 0.35,
            "is_active": True,
        },
    )
    assert create.status_code == 201
    zone_id = create.json()["data"]["zone_id"]

    listed = await client.get("/api/v1/zones", headers=admin)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    updated = await client.put(
        f"/api/v1/zones/{zone_id}", headers=admin, json={"line_y": 0.4, "name": "Red"}
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["line_y"] == 0.4
    assert updated.json()["data"]["name"] == "Red"

    deleted = await client.delete(f"/api/v1/zones/{zone_id}", headers=admin)
    assert deleted.status_code == 200

    empty = await client.get("/api/v1/zones", headers=admin)
    assert empty.json()["data"] == []


@pytest.mark.asyncio
async def test_zone_requires_valid_camera(client, token_for):
    resp = await client.post(
        "/api/v1/zones",
        headers=token_for("admin"),
        json={
            "name": "Ghost",
            "camera_id": "00000000-0000-0000-0000-000000000000",
            "severity": "danger",
            "line_y": 0.3,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_zone_line_y_validation(client, token_for):
    admin = token_for("admin")
    camera_id = await _camera(client, admin)
    resp = await client.post(
        "/api/v1/zones",
        headers=admin,
        json={"name": "Bad", "camera_id": camera_id, "severity": "danger", "line_y": 5},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
