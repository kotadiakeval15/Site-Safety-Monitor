"""Encrypted-login flow: public key endpoint + RSA-OAEP password envelope."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def _encrypt(password: str, public_key_pem: str) -> str:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    ciphertext = public_key.encrypt(  # type: ignore[union-attr]
        password.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode("ascii")


@pytest.mark.asyncio
async def test_public_key_endpoint_is_public(client):
    resp = await client.get("/api/v1/auth/public-key")
    assert resp.status_code == 200
    pem = resp.json()["data"]["public_key"]
    assert "BEGIN PUBLIC KEY" in pem


@pytest.mark.asyncio
async def test_encrypted_login_succeeds(client, users, password):
    pem = (await client.get("/api/v1/auth/public-key")).json()["data"]["public_key"]
    encrypted = _encrypt(password, pem)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": users["admin"]["email"], "password": encrypted, "encrypted": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_encrypted_login_rejects_garbage(client, users):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": users["admin"]["email"], "password": "not-encrypted", "encrypted": True},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_plaintext_login_still_works(client, users, password):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": users["admin"]["email"], "password": password},
    )
    assert resp.status_code == 200
