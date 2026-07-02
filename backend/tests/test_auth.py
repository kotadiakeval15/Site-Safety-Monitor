"""Authentication endpoint tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_success(client, users, password):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": users["admin"]["email"], "password": password},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access_token"]
    assert body["data"]["user"]["role"] == "admin"
    assert body["meta"]["request_id"]


@pytest.mark.asyncio
async def test_login_wrong_password(client, users):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": users["admin"]["email"], "password": "wrong"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_me_requires_token(client, users):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_me_returns_profile(client, token_for):
    resp = await client.get("/api/v1/auth/me", headers=token_for("viewer"))
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "viewer@example.com"
