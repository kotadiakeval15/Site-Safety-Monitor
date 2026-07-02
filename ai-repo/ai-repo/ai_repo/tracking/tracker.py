"""ByteTrack wrapper assigning stable worker ids.

One :class:`Tracker` instance is created per camera worker process, so worker
ids never collide across cameras (a bug in the original single-global-tracker
inference service).
"""

from __future__ import annotations

import supervision as sv


class Tracker:
    """Thin wrapper over ``supervision.ByteTrack``."""

    def __init__(self) -> None:
        self._tracker = sv.ByteTrack()

    def update(self, detections: sv.Detections) -> sv.Detections:
        """Assign / update tracker ids for the given detections."""

        if len(detections) == 0:
            return detections
        return self._tracker.update_with_detections(detections)
