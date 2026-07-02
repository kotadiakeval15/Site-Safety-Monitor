"""Authentication and user-management business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import get_password_cipher
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.enums import Role
from app.exceptions.base import ConflictError, UnauthorizedError
from app.models.user import User
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead

logger = get_logger(__name__)


class AuthService:
    """Handles login, token issuance and admin seeding."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._audit = AuditRepository(session)

    async def seed_admin_if_needed(self) -> None:
        """Create the SUPER_ADMIN account on first startup."""

        settings = get_settings()
        existing = await self._users.get_by_email(settings.admin_email)
        if existing is not None:
            return
        admin = User(
            name=settings.admin_name,
            email=settings.admin_email.lower(),
            password_hash=hash_password(settings.admin_password),
            role=Role.SUPER_ADMIN,
            is_active=True,
        )
        await self._users.add(admin)
        logger.info("Seeded SUPER_ADMIN account %s", settings.admin_email)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        """Validate credentials and issue a JWT.

        When ``payload.encrypted`` is set, the password is an RSA-OAEP envelope
        produced by the frontend and is decrypted before verification.
        """

        password = (
            get_password_cipher().decrypt(payload.password)
            if payload.encrypted
            else payload.password
        )
        user = await self._users.get_by_email(payload.email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")

        token = create_access_token(
            user.user_id,
            extra_claims={"email": user.email, "role": user.role.value, "name": user.name},
        )
        await self._audit.record("auth.login", user.user_id, {"email": user.email})
        return TokenResponse(
            access_token=token,
            expires_in_hours=get_settings().jwt_expire_hours,
            user=UserRead.model_validate(user),
        )

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("User not found")
        return user

    async def create_user(self, payload: UserCreate, actor_id: UUID) -> UserRead:
        """Create a new user (SUPER_ADMIN only, enforced at the route)."""

        if await self._users.get_by_email(payload.email) is not None:
            raise ConflictError("A user with that email already exists")
        user = User(
            name=payload.name,
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=True,
        )
        await self._users.add(user)
        await self._audit.record(
            "user.create", actor_id, {"email": user.email, "role": user.role.value}
        )
        return UserRead.model_validate(user)

    async def list_users(self) -> list[UserRead]:
        users = await self._users.list_all()
        return [UserRead.model_validate(u) for u in users]
