"""Rate-limit behaviour tests for the sliding-window limiter."""

from __future__ import annotations

import pytest
from app.core.rate_limit import SlidingWindowLimiter, parse_rate


def test_parse_rate():
    assert parse_rate("10/minute") == (10, 60)
    assert parse_rate("5/second") == (5, 1)
    assert parse_rate("100/hour") == (100, 3600)


def test_sliding_window_blocks_over_limit():
    limiter = SlidingWindowLimiter()
    assert all(limiter.hit("k", 3, 60) for _ in range(3))
    assert limiter.hit("k", 3, 60) is False


def test_sliding_window_is_per_key():
    limiter = SlidingWindowLimiter()
    assert limiter.hit("a", 1, 60) is True
    assert limiter.hit("a", 1, 60) is False
    assert limiter.hit("b", 1, 60) is True


class _FakeClient:
    host = "1.2.3.4"


class _FakeURL:
    path = "/api/v1/auth/login"


class _FakeRequest:
    client = _FakeClient()
    url = _FakeURL()


@pytest.mark.asyncio
async def test_rate_limit_dependency_raises_after_limit(monkeypatch):
    from app.core import rate_limit as rl
    from app.exceptions.base import RateLimitError

    monkeypatch.setattr(rl.get_settings(), "rate_limit_enabled", True, raising=False)
    dep = rl.rate_limit("2/minute")
    request = _FakeRequest()

    await dep(request)
    await dep(request)
    with pytest.raises(RateLimitError):
        await dep(request)
