"""Role-based access control tests."""

from __future__ import annotations

import pytest


async def _make_camera(client, headers) -> str:
    resp = await client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "Cam", "source_type": "file", "stream_url": "/data/x.mp4"},
    )
    assert resp.status_code == 201
    return resp.json()["data"]["camera_id"]


@pytest.mark.asyncio
async def test_viewer_cannot_create_camera(client, token_for):
    resp = await client.post(
        "/api/v1/cameras",
        headers=token_for("viewer"),
        json={"name": "Cam", "source_type": "file", "stream_url": "/data/x.mp4"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_can_create_camera(client, token_for):
    camera_id = await _make_camera(client, token_for("admin"))
    assert camera_id


@pytest.mark.asyncio
async def test_viewer_can_read_cameras(client, token_for):
    resp = await client.get("/api/v1/cameras", headers=token_for("viewer"))
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_viewer_cannot_access_audit(client, token_for):
    resp = await client.get("/api/v1/audit", headers=token_for("viewer"))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_only_super_admin_lists_users(client, token_for):
    denied = await client.get("/api/v1/auth/users", headers=token_for("admin"))
    assert denied.status_code == 403
    allowed = await client.get("/api/v1/auth/users", headers=token_for("super"))
    assert allowed.status_code == 200
