"""Authentication and user DTOs."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.enums import Role
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    """Login credentials.

    ``password`` carries the RSA-OAEP encrypted, base64-encoded password when
    ``encrypted`` is true (the default path for the web UI). Direct API/test
    clients may send a plaintext password with ``encrypted`` omitted/false.
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    encrypted: bool = False


class TokenResponse(BaseModel):
    """JWT issued on successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
    user: UserRead


class UserRead(ORMModel):
    """User read DTO (never exposes the password hash)."""

    user_id: uuid.UUID
    name: str
    email: EmailStr
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    """Payload to create a new user (SUPER_ADMIN only)."""

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.VIEWER


TokenResponse.model_rebuild()
