"""Detection statistics controller."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_viewer
from app.models.user import User
from app.responses import success_response
from app.services.statistics_service import StatisticsService

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("")
async def get_statistics(
    session: DbSession,
    _user: User = Depends(require_viewer),
    window_hours: int = Query(default=24, ge=1, le=8760),
) -> dict:
    """Return aggregated detection analytics for the requested time window."""

    stats = await StatisticsService(session).get_statistics(window_hours)
    return success_response(stats.model_dump(mode="json"))
