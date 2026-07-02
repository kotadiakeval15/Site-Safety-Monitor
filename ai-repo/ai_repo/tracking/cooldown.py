"""Alert cooldown tracking (pure-Python, no CV dependency)."""

from __future__ import annotations

import time


class CooldownTracker:
    """Suppress duplicate alerts for the same worker/event within a window."""

    def __init__(self, cooldown_seconds: float) -> None:
        self._cooldown = cooldown_seconds
        self._last_fired: dict[tuple[int, str, str], float] = {}

    def should_fire(self, worker_id: int, event_type: str, sub_key: str = "") -> bool:
        """Return True if enough time has elapsed to fire this event again."""

        key = (worker_id, event_type, sub_key)
        now = time.monotonic()
        last = self._last_fired.get(key, 0.0)
        if now - last >= self._cooldown:
            self._last_fired[key] = now
            return True
        return False

    def reset(self, worker_id: int, event_type: str, sub_key: str = "") -> None:
        """Clear cooldown so the next check can fire immediately."""

        self._last_fired.pop((worker_id, event_type, sub_key), None)
