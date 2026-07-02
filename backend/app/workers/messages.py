"""Picklable IPC payloads exchanged between the backend and worker processes.

This module intentionally avoids heavy imports (cv2, torch, ...) so that the
API process can import it without the CV stack installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkerLineConfig:
    """One severity line segment for a camera, mapped back to its zone.

    ``(x1, y1)`` and ``(x2, y2)`` are normalized (0..1) endpoints defining the
    oriented line drawn on the floor.
    """

    color: str  # "green" | "yellow" | "red"
    severity: str  # ZoneSeverity value
    x1: float = 0.0
    y1: float = 0.5
    x2: float = 1.0
    y2: float = 0.5
    zone_id: str | None = None


@dataclass
class WorkerConfig:
    """Everything a child worker needs to run without touching the database."""

    camera_id: str
    stream_url: str
    lines: list[WorkerLineConfig] = field(default_factory=list)
    yolo_model_path: str = "yolov8n.pt"
    helmet_model_path: str | None = None
    confidence: float = 0.45
    device: str = "cpu"
    frame_skip: int = 2
    cooldown_seconds: float = 10.0
    live_frames_dir: str = "/data/live"
    show_window: bool = False
    detection_mode: str = "restricted_area"

    def line_items(self) -> list[dict]:
        """Return the zone-derived line segments for the AI pipeline."""

        return [
            {
                "color": line.color,
                "x1": line.x1,
                "y1": line.y1,
                "x2": line.x2,
                "y2": line.y2,
            }
            for line in self.lines
        ]

    def zone_for_line(self, color: str) -> str | None:
        for line in self.lines:
            if line.color == color:
                return line.zone_id
        return None


@dataclass
class DetectionMessage:
    """A single detection event streamed from a worker to the backend."""

    camera_id: str
    worker_id: int
    violation_type: str  # ViolationType value
    severity: str  # ZoneSeverity value
    crossed_line: str | None = None
    confidence: float = 0.0
    bbox: list[int] | None = None
    foot_x: float | None = None
    foot_y: float | None = None
    screenshot_base64: str | None = None
    message: str | None = None
    zone_id: str | None = None
