"""Datetime helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return a timezone-aware UTC now."""

    return datetime.now(UTC)


def isoformat(value: datetime | None) -> str | None:
    """Return an ISO-8601 string for ``value`` (``None`` passes through)."""

    return value.isoformat() if value is not None else None
