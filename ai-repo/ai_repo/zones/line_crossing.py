"""Safety-line crossing, zone occupancy, and helmet association."""

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
    """A single severity line as a segment in normalized (0..1) frame coords."""

    color: str  # "green" | "yellow" | "red"
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class LineConfig:
    """Safety-line segments derived from a camera's active zones."""

    lines: list[SafetyLine] = field(default_factory=list)

    @classmethod
    def from_items(cls, items: list[dict]) -> LineConfig:
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
    zone_color: str = "safe"

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
            "zone_color": self.zone_color,
        }


class HelmetAssociator:
    """Associate helmet detections with person bounding boxes."""

    HEAD_RATIO = 0.45
    MIN_HEAD_HELMET_IOU = 0.08

    @staticmethod
    def compute_foot(bbox: BBox) -> tuple[float, float]:
        x1, _y1, x2, y2 = bbox
        return (x1 + x2) / 2.0, float(y2)

    @classmethod
    def _head_region(cls, person_bbox: BBox) -> BBox:
        x1, y1, x2, y2 = person_bbox
        head_y2 = int(y1 + (y2 - y1) * cls.HEAD_RATIO)
        return x1, y1, x2, head_y2

    @staticmethod
    def _bbox_iou(a: BBox, b: tuple[float, float, float, float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter / union

    def evaluate_helmet_status(
        self,
        person_bbox: BBox,
        helmets: list,
    ) -> tuple[bool, float]:
        """Return current helmet compliance for one person (fresh each frame)."""

        head = self._head_region(person_bbox)
        hx1, hy1, hx2, hy2 = head
        px1, py1, px2, py2 = person_bbox
        best_compliant = 0.0
        best_violation = 0.0
        for helmet in helmets:
            helmet_bbox = (helmet.x1, helmet.y1, helmet.x2, helmet.y2)
            centroid_in_head = hx1 <= helmet.cx <= hx2 and hy1 <= helmet.cy <= hy2
            centroid_in_person = px1 <= helmet.cx <= px2 and py1 <= helmet.cy <= py2
            overlaps_head = self._bbox_iou(head, helmet_bbox) >= self.MIN_HEAD_HELMET_IOU
            overlaps_person = self._bbox_iou(person_bbox, helmet_bbox) >= 0.05
            if not (centroid_in_head or centroid_in_person or overlaps_head or overlaps_person):
                continue
            if helmet.is_compliant:
                best_compliant = max(best_compliant, float(helmet.conf))
            else:
                best_violation = max(best_violation, float(helmet.conf))
        if best_compliant > 0.0 and best_compliant >= best_violation:
            return True, best_compliant
        return False, max(best_violation, best_compliant)

    def has_helmet(
        self, person_bbox: BBox, helmet_centroids: list[tuple[float, float, float]]
    ) -> tuple[bool, float]:
        """Backward-compatible wrapper for legacy centroid-only helmet lists."""

        legacy = [
            type(
                "LegacyHelmet",
                (),
                {
                    "cx": hx,
                    "cy": hy,
                    "conf": conf,
                    "x1": hx,
                    "y1": hy,
                    "x2": hx,
                    "y2": hy,
                    "is_compliant": True,
                },
            )()
            for hx, hy, conf in helmet_centroids
        ]
        return self.evaluate_helmet_status(person_bbox, legacy)


PixelPoint = tuple[int, int]
_Segment = tuple[CrossedLine, tuple[float, float], tuple[float, float], int]


class LineCrossingDetector:
    """Detect line crossings and classify current zone occupancy by foot position."""

    _COLOR_ENUM: ClassVar[dict[str, CrossedLine]] = {
        "red": CrossedLine.RED,
        "yellow": CrossedLine.YELLOW,
        "green": CrossedLine.GREEN,
    }
    _SPAN_MARGIN = 0.08

    def __init__(self, line_config: LineConfig, frame_width: int, frame_height: int) -> None:
        order = {"red": 0, "yellow": 1, "green": 2}
        self._cam_ref = (frame_width / 2.0, frame_height * 0.95)
        self._segments: list[_Segment] = []
        for line in sorted(line_config.lines, key=lambda ln: order.get(ln.color, 99)):
            enum = self._COLOR_ENUM.get(line.color)
            if enum is None:
                continue
            p1 = (line.x1 * frame_width, line.y1 * frame_height)
            p2 = (line.x2 * frame_width, line.y2 * frame_height)
            camera_sign = self._camera_sign(p1, p2)
            self._segments.append((enum, p1, p2, camera_sign))
        self._previous_side: dict[tuple[int, int], float] = {}

    def _camera_sign(self, p1: tuple[float, float], p2: tuple[float, float]) -> int:
        """Sign of the half-plane on the camera / near side of the line."""

        side = self._side(p1, p2, self._cam_ref)
        if side > 0:
            return 1
        if side < 0:
            return -1
        return 1

    @staticmethod
    def _side(p1: tuple[float, float], p2: tuple[float, float], f: tuple[float, float]) -> float:
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

    def _line_side(self, foot: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return self._side(p1, p2, foot)

    def _on_near_side(
        self, foot: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], camera_sign: int
    ) -> bool:
        return self._line_side(foot, p1, p2) * camera_sign > 0

    def _on_far_side(
        self, foot: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], camera_sign: int
    ) -> bool:
        return self._line_side(foot, p1, p2) * camera_sign < 0

    def classify_zone(self, foot_x: float, foot_y: float) -> str:
        """Return the zone band for a foot point.

        Lines are ordered far → near: green, yellow, red (toward the camera).
        - Before green and between green/yellow: safe (no alert)
        - Between yellow/red: warning
        - After red toward the camera: restricted
        """

        foot = (foot_x, foot_y)
        by_color: dict[str, tuple[tuple[float, float], tuple[float, float], int]] = {}
        for enum, p1, p2, camera_sign in self._segments:
            by_color[enum.value] = (p1, p2, camera_sign)

        def near(color: str) -> bool | None:
            segment = by_color.get(color)
            if segment is None:
                return None
            p1, p2, camera_sign = segment
            return self._on_near_side(foot, p1, p2, camera_sign)

        def far(color: str) -> bool | None:
            segment = by_color.get(color)
            if segment is None:
                return None
            p1, p2, camera_sign = segment
            return self._on_far_side(foot, p1, p2, camera_sign)

        if near("red") is True:
            return "red"
        if near("yellow") is True and far("red") is not False:
            return "yellow"
        if near("green") is True and far("yellow") is not False:
            return "safe"
        if far("green") is not False:
            return "safe"
        return "safe"

    def evaluate(self, worker_id: int, foot_x: float, foot_y: float) -> list[CrossedLine]:
        crossed: list[CrossedLine] = []
        foot = (foot_x, foot_y)
        for idx, (enum, p1, p2, _danger) in enumerate(self._segments):
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
        for key in [k for k in self._previous_side if k[0] not in active_ids]:
            self._previous_side.pop(key, None)

    def segments(self) -> list[tuple[str, PixelPoint, PixelPoint]]:
        return [
            (enum.value, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])))
            for enum, p1, p2, _ in self._segments
        ]
