"""Camera CRUD + activation tests (worker supervisor is faked)."""

from __future__ import annotations

import pytest


class FakeSupervisor:
    """In-memory stand-in for the multiprocessing supervisor."""

    def __init__(self) -> None:
        self._active: set[str] = set()

    def activate(self, config) -> None:
        self._active.add(config.camera_id)

    def deactivate(self, camera_id: str) -> bool:
        self._active.discard(camera_id)
        return True

    def is_running(self, camera_id: str) -> bool:
        return camera_id in self._active


@pytest.fixture(autouse=True)
def fake_supervisor(monkeypatch):
    supervisor = FakeSupervisor()
    monkeypatch.setattr("app.services.camera_service.get_supervisor", lambda: supervisor)
    return supervisor


async def _create(client, headers) -> str:
    resp = await client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "Gate", "source_type": "file", "stream_url": "/data/demo.mp4"},
    )
    return resp.json()["data"]["camera_id"]


@pytest.mark.asyncio
async def test_camera_crud(client, token_for):
    admin = token_for("admin")
    camera_id = await _create(client, admin)

    got = await client.get(f"/api/v1/cameras/{camera_id}", headers=admin)
    assert got.status_code == 200
    assert got.json()["data"]["status"] == "inactive"

    updated = await client.put(
        f"/api/v1/cameras/{camera_id}", headers=admin, json={"name": "Main Gate"}
    )
    assert updated.json()["data"]["name"] == "Main Gate"

    deleted = await client.delete(f"/api/v1/cameras/{camera_id}", headers=admin)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_camera_activate_deactivate(client, token_for, fake_supervisor):
    admin = token_for("admin")
    camera_id = await _create(client, admin)

    activated = await client.post(f"/api/v1/cameras/{camera_id}/activate", headers=admin)
    assert activated.status_code == 200
    assert activated.json()["data"]["status"] == "active"
    assert fake_supervisor.is_running(camera_id)

    deactivated = await client.post(f"/api/v1/cameras/{camera_id}/deactivate", headers=admin)
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["status"] == "inactive"
    assert not fake_supervisor.is_running(camera_id)


@pytest.mark.asyncio
async def test_camera_detection_mode_defaults_and_updates(client, token_for):
    admin = token_for("admin")
    camera_id = await _create(client, admin)

    got = await client.get(f"/api/v1/cameras/{camera_id}", headers=admin)
    assert got.json()["data"]["detection_mode"] == "restricted_area"

    updated = await client.put(
        f"/api/v1/cameras/{camera_id}", headers=admin, json={"detection_mode": "helmet"}
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["detection_mode"] == "helmet"


@pytest.mark.asyncio
async def test_camera_video_upload_and_stream(client, token_for):
    admin = token_for("admin")
    camera_id = await _create(client, admin)

    payload = b"\x00\x00\x00\x18ftypmp42" + b"fake-video-bytes" * 64
    upload = await client.post(
        f"/api/v1/cameras/{camera_id}/video",
        headers=admin,
        files={"file": ("demo.mp4", payload, "video/mp4")},
    )
    assert upload.status_code == 200
    data = upload.json()["data"]
    assert data["has_video"] is True
    assert data["source_type"] == "file"

    full = await client.get(f"/api/v1/cameras/{camera_id}/video", headers=admin)
    assert full.status_code == 200
    assert full.content == payload

    ranged = await client.get(
        f"/api/v1/cameras/{camera_id}/video", headers={**admin, "Range": "bytes=0-7"}
    )
    assert ranged.status_code == 206
    assert ranged.content == payload[:8]
    assert ranged.headers["content-range"] == f"bytes 0-7/{len(payload)}"


@pytest.mark.asyncio
async def test_camera_video_rejects_bad_extension(client, token_for):
    admin = token_for("admin")
    camera_id = await _create(client, admin)
    resp = await client.post(
        f"/api/v1/cameras/{camera_id}/video",
        headers=admin,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_get_missing_camera_returns_404(client, token_for):
    resp = await client.get(
        "/api/v1/cameras/00000000-0000-0000-0000-000000000000", headers=token_for("admin")
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
