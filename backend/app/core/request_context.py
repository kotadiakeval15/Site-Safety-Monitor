"""Per-request context propagated through a ``ContextVar``.

Used by the logging layer and the response envelope so that every log line and
API response carries the same ``request_id``.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Generate a short unique request id."""

    return uuid.uuid4().hex


def set_request_id(request_id: str) -> None:
    """Bind ``request_id`` to the current context."""

    _request_id_ctx.set(request_id)


def get_request_id() -> str:
    """Return the request id bound to the current context (``"-"`` if unset)."""

    return _request_id_ctx.get()
