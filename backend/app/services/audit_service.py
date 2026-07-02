"""Audit log read business logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repo import AuditRepository


class AuditService:
    """Exposes recent audit log entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditRepository(session)

    async def list_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        logs = await self._audit.list_recent(limit)
        return [
            {
                "log_id": str(log.log_id),
                "action": log.action,
                "user_id": str(log.user_id) if log.user_id else None,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
