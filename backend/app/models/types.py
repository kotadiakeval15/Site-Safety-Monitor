"""Portable column helpers usable on both PostgreSQL and SQLite (tests)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
JSONColumn = JSON().with_variant(JSONB(), "postgresql")


def enum_column(enum_cls: type[Enum]) -> SAEnum:
    """Return a VARCHAR-backed enum column storing member values.

    ``native_enum=False`` keeps the schema portable and avoids PostgreSQL
    ``CREATE TYPE`` churn in migrations while still enforcing a CHECK
    constraint on the allowed values.
    """

    return SAEnum(
        enum_cls,
        values_callable=lambda enum: [member.value for member in enum],  # type: ignore[arg-type]
        native_enum=False,
        validate_strings=True,
    )


def _noop() -> Any:  # pragma: no cover - placeholder for future helpers
    return None
