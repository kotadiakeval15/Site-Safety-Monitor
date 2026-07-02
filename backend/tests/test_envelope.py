"""Response envelope + health + error-mapping tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_envelope(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"success", "message", "data", "error", "meta"}
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["meta"]["request_id"]
    assert resp.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_not_found_envelope(client, token_for):
    resp = await client.get(
        "/api/v1/zones/00000000-0000-0000-0000-000000000000", headers=token_for("viewer")
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["data"] is None


@pytest.mark.asyncio
async def test_validation_error_envelope(client, token_for):
    resp = await client.post(
        "/api/v1/cameras",
        headers=token_for("admin"),
        json={"name": "", "source_type": "banana", "stream_url": ""},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_pagination_meta(client, token_for):
    resp = await client.get(
        "/api/v1/detections", headers=token_for("viewer"), params={"page": 1, "page_size": 5}
    )
    pagination = resp.json()["meta"]["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 5
    assert "total_pages" in pagination
