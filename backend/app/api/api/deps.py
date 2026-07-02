"""FastAPI dependency-injection helpers: sessions, auth, RBAC, pagination."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.enums import Role, role_at_least
from app.exceptions.base import ForbiddenError, UnauthorizedError
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.pagination import PageParams

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """Resolve and validate the authenticated user from the Bearer token."""

    if credentials is None:
        raise UnauthorizedError("Missing authentication token")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
    user = await UserRepository(session).get_by_id(UUID(user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(
    minimum: Role,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Return a dependency enforcing a minimum role level."""

    async def _guard(user: CurrentUser) -> User:
        if not role_at_least(user.role, minimum):
            raise ForbiddenError(f"Requires at least '{minimum.value}' role")
        return user

    return _guard


# Convenience role guards.
require_viewer = require_roles(Role.VIEWER)
require_admin = require_roles(Role.ADMIN)
require_super_admin = require_roles(Role.SUPER_ADMIN)


def pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    """Extract pagination parameters from the query string."""

    return PageParams(page=page, page_size=page_size)


PaginationDep = Annotated[PageParams, Depends(pagination_params)]
