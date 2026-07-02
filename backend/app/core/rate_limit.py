"""Per-route rate limiting via a dependency-based sliding-window limiter.

Implemented as a FastAPI dependency (rather than a decorator) so it composes
cleanly with typed body/session parameters and raises the standard
:class:`RateLimitError` mapped to the response envelope.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.config import get_settings
from app.exceptions.base import RateLimitError

_UNIT_SECONDS = {
    "second": 1,
    "sec": 1,
    "s": 1,
    "minute": 60,
    "min": 60,
    "m": 60,
    "hour": 3600,
    "h": 3600,
    "day": 86400,
}


def parse_rate(spec: str) -> tuple[int, int]:
    """Parse a ``"10/minute"`` style spec into ``(limit, window_seconds)``."""

    count_str, _, unit = spec.partition("/")
    limit = int(count_str.strip())
    window = _UNIT_SECONDS.get(unit.strip().lower(), 60)
    return limit, window


class SlidingWindowLimiter:
    """In-memory sliding-window counter keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window: int) -> bool:
        """Register a hit; return True if allowed, False if over the limit."""

        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_limiter = SlidingWindowLimiter()


def rate_limit(spec: str) -> Callable[[Request], Awaitable[None]]:
    """Return a dependency enforcing ``spec`` (e.g. ``"10/minute"``) per client IP."""

    limit, window = parse_rate(spec)

    async def _dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        client_ip = request.client.host if request.client else "anonymous"
        key = f"{request.url.path}:{client_ip}"
        if not _limiter.hit(key, limit, window):
            raise RateLimitError(f"Rate limit exceeded ({spec})")

    return _dependency
