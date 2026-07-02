"""Audit log controller."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_admin
from app.models.user import User
from app.responses import success_response
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_logs(
    session: DbSession,
    _admin: User = Depends(require_admin),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    logs = await AuditService(session).list_logs(limit)
    return success_response(logs)
