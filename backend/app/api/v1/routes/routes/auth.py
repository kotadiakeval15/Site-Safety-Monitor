"""Authentication controller."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_super_admin
from app.core.config import get_settings
from app.core.crypto import get_password_cipher
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.responses import success_response
from app.schemas.auth import LoginRequest, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

login_rate_limit = rate_limit(get_settings().rate_limit_login)


@router.get("/public-key")
async def public_key() -> dict:
    """Return the RSA public key used to encrypt the password before login."""

    return success_response({"public_key": get_password_cipher().public_key_pem()})


@router.post("/login", dependencies=[Depends(login_rate_limit)])
async def login(payload: LoginRequest, session: DbSession) -> dict:
    """Authenticate and return a JWT (rate limited)."""

    token = await AuthService(session).login(payload)
    return success_response(token.model_dump(mode="json"), message="Login successful")


@router.get("/me")
async def me(current_user: CurrentUser) -> dict:
    """Return the authenticated user's profile."""

    return success_response(UserRead.model_validate(current_user).model_dump(mode="json"))


@router.get("/users")
async def list_users(
    session: DbSession,
    _admin: User = Depends(require_super_admin),
) -> dict:
    """List all users (SUPER_ADMIN only)."""

    users = await AuthService(session).list_users()
    return success_response([u.model_dump(mode="json") for u in users])


@router.post("/users", status_code=201)
async def create_user(
    payload: UserCreate,
    session: DbSession,
    admin: User = Depends(require_super_admin),
) -> dict:
    """Create a new user (SUPER_ADMIN only)."""

    user = await AuthService(session).create_user(payload, admin.user_id)
    return success_response(user.model_dump(mode="json"), message="User created")
