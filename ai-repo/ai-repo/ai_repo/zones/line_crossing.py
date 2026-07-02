"""Horizontal safety-line crossing and helmet association.

Ported verbatim (behaviour preserved) from the original inference-service
engine. Pure-Python: no OpenCV / numpy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

BBox = tuple[int, int, int, int]


class HelmetStatus(str, Enum):
    """Whether a worker is wearing a helmet."""

    SAFE = "safe"
    VIOLATION = "helmet_violation"


class CrossedLine(str, Enum):
    """The color of a crossed safety line."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class SafetyLine:
    """A single severity line as a segment in normalized (0..1) frame coords.

    ``(x1, y1)`` and ``(x2, y2)`` are the two endpoints; the operator aligns them
    to the floor so the line can follow the floor's perspective at any angle.
    """

    color: str  # "green" | "yellow" | "red"
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class LineConfig:
    """The set of safety-line segments derived from a camera's active zones.

    Only the lines present here are drawn and evaluated, so the view mirrors
    exactly the zones an operator created.
    """

    lines: list[SafetyLine] = field(default_factory=list)

    @classmethod
    def from_items(cls, items: list[dict]) -> LineConfig:
        """Build a config from ``[{color, x1, y1, x2, y2}, ...]`` items."""

        return cls(
            [
                SafetyLine(
                    color=str(it["color"]),
                    x1=float(it["x1"]),
                    y1=float(it["y1"]),
                    x2=float(it["x2"]),
                    y2=float(it["y2"]),
                )
                for it in items
            ]
        )


@dataclass
class WorkerDetection:
    """A single tracked worker and its safety evaluation for one frame."""

    worker_id: int
    bbox: BBox
    confidence: float
    foot_x: float
    foot_y: float
    helmet_status: HelmetStatus
    helmet_confidence: float = 0.0
    crossed_lines: list[CrossedLine] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "foot_x": self.foot_x,
            "foot_y": self.foot_y,
            "helmet_status": self.helmet_status.value,
            "helmet_confidence": self.helmet_confidence,
            "crossed_lines": [c.value for c in self.crossed_lines],
        }


class HelmetAssociator:
    """Associate helmet detections with person bounding boxes."""

    UPPER_BODY_RATIO = 0.4

    @staticmethod
    def compute_foot(bbox: BBox) -> tuple[float, float]:
        """Return the bottom-center (foot) point of a bbox."""

        x1, _y1, x2, y2 = bbox
        return (x1 + x2) / 2.0, float(y2)

    def has_helmet(
        self, person_bbox: BBox, helmet_centroids: list[tuple[float, float, float]]
    ) -> tuple[bool, float]:
        """Return (has_helmet, confidence) using the upper-body head region."""

        x1, y1, x2, y2 = person_bbox
        upper_limit = y1 + (y2 - y1) * self.UPPER_BODY_RATIO
        best_conf = 0.0
        for hx, hy, conf in helmet_centroids:
            if x1 <= hx <= x2 and y1 <= hy <= upper_limit:
                best_conf = max(best_conf, conf)
                return True, best_conf
        return False, best_conf


PixelPoint = tuple[int, int]
_Segment = tuple[CrossedLine, tuple[float, float], tuple[float, float]]


class LineCrossingDetector:
    """Detect crossings of oriented safety-line *segments* by the foot point.

    Each line is a segment ``P1->P2``. A worker crosses it when the signed side
    of the foot relative to the segment flips sign between frames, and the foot
    projects onto the segment span (so crossing the infinite line far outside
    the drawn segment does not count).
    """

    _COLOR_ENUM: ClassVar[dict[str, CrossedLine]] = {
        "red": CrossedLine.RED,
        "yellow": CrossedLine.YELLOW,
        "green": CrossedLine.GREEN,
    }
    # Allow the foot to be slightly past the drawn endpoints and still count.
    _SPAN_MARGIN = 0.08

    def __init__(self, line_config: LineConfig, frame_width: int, frame_height: int) -> None:
        # Stable red -> yellow -> green ordering for deterministic evaluation.
        order = {"red": 0, "yellow": 1, "green": 2}
        self._segments: list[_Segment] = []
        for line in sorted(line_config.lines, key=lambda ln: order.get(ln.color, 99)):
            enum = self._COLOR_ENUM.get(line.color)
            if enum is None:
                continue
            p1 = (line.x1 * frame_width, line.y1 * frame_height)
            p2 = (line.x2 * frame_width, line.y2 * frame_height)
            self._segments.append((enum, p1, p2))
        self._previous_side: dict[tuple[int, int], float] = {}

    @staticmethod
    def _side(p1: tuple[float, float], p2: tuple[float, float], f: tuple[float, float]) -> float:
        """Signed area (cross product) of the foot relative to the segment."""

        return (p2[0] - p1[0]) * (f[1] - p1[1]) - (p2[1] - p1[1]) * (f[0] - p1[0])

    @classmethod
    def _within_span(
        cls, p1: tuple[float, float], p2: tuple[float, float], f: tuple[float, float]
    ) -> bool:
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return False
        t = ((f[0] - p1[0]) * dx + (f[1] - p1[1]) * dy) / length_sq
        return -cls._SPAN_MARGIN <= t <= 1.0 + cls._SPAN_MARGIN

    def evaluate(self, worker_id: int, foot_x: float, foot_y: float) -> list[CrossedLine]:
        """Return the line segments the foot crossed on this frame."""

        crossed: list[CrossedLine] = []
        foot = (foot_x, foot_y)
        for idx, (enum, p1, p2) in enumerate(self._segments):
            side = self._side(p1, p2, foot)
            key = (worker_id, idx)
            prev = self._previous_side.get(key)
            self._previous_side[key] = side
            if prev is None:
                continue
            flipped = (prev < 0 <= side) or (prev > 0 >= side)
            if flipped and self._within_span(p1, p2, foot):
                crossed.append(enum)
        return crossed

    def prune(self, active_ids: set[int]) -> None:
        """Drop foot-history for workers no longer in frame."""

        for key in [k for k in self._previous_side if k[0] not in active_ids]:
            self._previous_side.pop(key, None)

    def segments(self) -> list[tuple[str, PixelPoint, PixelPoint]]:
        """Return (color, p1, p2) in pixel coordinates for annotation."""

        return [
            (enum.value, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])))
            for enum, p1, p2 in self._segments
        ]
