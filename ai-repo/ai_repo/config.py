"""Standalone configuration for running the AI package outside the backend.

The backend injects a fully-populated ``WorkerConfig`` into each worker, so this
module is only used when driving the pipeline directly (e.g. from a script).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AiSettings:
    """Model and inference configuration."""

    yolo_model_path: str = "yolov8n.pt"
    helmet_model_path: str | None = None
    confidence_threshold: float = 0.45
    device: str = "cpu"
    frame_skip: int = 2
    green_line_y: float = 0.55
    yellow_line_y: float = 0.45
    red_line_y: float = 0.35
