"""Health check controller."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings
from app.responses import success_response
from app.utils.datetime import utcnow

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: DbSession) -> dict:
    """Return service and database health (unauthenticated)."""

    settings = get_settings()
    database_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    return success_response(
        {
            "status": "ok" if database_ok else "degraded",
            "database": "up" if database_ok else "down",
            "version": settings.app_version,
            "timestamp": utcnow().isoformat(),
        }
    )
