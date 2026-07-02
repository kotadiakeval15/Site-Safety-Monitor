"""Tracking utilities.

Only the light-weight :class:`CooldownTracker` is exported here so that
``from ai_repo.tracking import CooldownTracker`` does not pull in ``supervision``.
Import :class:`Tracker` directly from ``ai_repo.tracking.tracker`` when the CV
stack is available.
"""

from ai_repo.tracking.cooldown import CooldownTracker

__all__ = ["CooldownTracker"]
