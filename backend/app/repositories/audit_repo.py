"""Audit log data-access layer."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    """Data access for :class:`AuditLog`."""

    model = AuditLog

    async def record(
        self, action: str, user_id: UUID | None, details: dict[str, Any] | None = None
    ) -> AuditLog:
        log = AuditLog(action=action, user_id=user_id, details=details)
        return await self.add(log)

    async def list_recent(self, limit: int = 200) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
