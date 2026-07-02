"""The end-to-end per-camera safety detection pipeline."""

from __future__ import annotations

import logging
from typing import ClassVar

import cv2
import numpy as np

from ai_repo.detection.detector import PersonHelmetDetector
from ai_repo.tracking.tracker import Tracker
from ai_repo.zones.line_crossing import (
    HelmetAssociator,
    HelmetStatus,
    LineConfig,
    LineCrossingDetector,
    WorkerDetection,
)

logger = logging.getLogger(__name__)


class SafetyPipeline:
    """YOLOv8 + ByteTrack pipeline for helmet and line-crossing detection."""

    def __init__(
        self,
        person_model_path: str = "yolov8n.pt",
        helmet_model_path: str | None = None,
        confidence: float = 0.45,
        device: str = "cpu",
    ) -> None:
        self._detector = PersonHelmetDetector(
            person_model_path=person_model_path,
            helmet_model_path=helmet_model_path,
            confidence=confidence,
            device=device,
        )
        self._tracker = Tracker()
        self._associator = HelmetAssociator()
        self._line_detectors: dict[tuple[int, int], LineCrossingDetector] = {}

    def _line_detector(
        self, line_config: LineConfig, frame_width: int, frame_height: int
    ) -> LineCrossingDetector:
        key = (frame_width, frame_height)
        detector = self._line_detectors.get(key)
        if detector is None:
            detector = LineCrossingDetector(line_config, frame_width, frame_height)
            self._line_detectors[key] = detector
        return detector

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        line_config: LineConfig,
        mode: str = "restricted_area",
    ) -> tuple[list[dict], np.ndarray]:
        height, width = frame.shape[:2]
        helmet_mode = mode == "helmet"
        persons = self._detector.detect_persons(frame)
        tracked = self._tracker.update(persons)
        helmets = self._detector.detect_helmets(frame) if helmet_mode else []
        line_detector = (
            None if helmet_mode else self._line_detector(line_config, width, height)
        )

        detections: list[WorkerDetection] = []
        active_ids: set[int] = set()

        if getattr(tracked, "tracker_id", None) is not None:
            for idx in range(len(tracked)):
                tid = tracked.tracker_id[idx]
                if tid is None:
                    continue
                worker_id = int(tid)
                active_ids.add(worker_id)
                bbox = tuple(int(v) for v in tracked.xyxy[idx])
                conf = (
                    float(tracked.confidence[idx])
                    if tracked.confidence is not None
                    else 0.0
                )
                foot_x, foot_y = self._associator.compute_foot(bbox)
                if helmet_mode:
                    has_helmet, helmet_conf = self._associator.evaluate_helmet_status(
                        bbox, helmets
                    )
                    status = HelmetStatus.SAFE if has_helmet else HelmetStatus.VIOLATION
                    crossed: list = []
                    zone_color = "safe"
                else:
                    helmet_conf = 0.0
                    status = HelmetStatus.SAFE
                    crossed = line_detector.evaluate(  # type: ignore[union-attr]
                        worker_id, foot_x, foot_y
                    )
                    zone_color = line_detector.classify_zone(foot_x, foot_y)  # type: ignore[union-attr]
                detections.append(
                    WorkerDetection(
                        worker_id=worker_id,
                        bbox=bbox,  # type: ignore[arg-type]
                        confidence=conf,
                        foot_x=foot_x,
                        foot_y=foot_y,
                        helmet_status=status,
                        helmet_confidence=helmet_conf,
                        crossed_lines=crossed,
                        zone_color=zone_color,
                    )
                )

        if line_detector is not None:
            line_detector.prune(active_ids)
        annotated = self._annotate(frame, detections, line_detector, helmet_mode)
        return [d.to_dict() for d in detections], annotated

    _LINE_COLORS: ClassVar[dict[str, tuple[int, int, int]]] = {
        "red": (0, 0, 255),
        "yellow": (0, 220, 255),
        "green": (0, 255, 0),
        "safe": (0, 200, 0),
    }

    @classmethod
    def _bbox_color(cls, det: WorkerDetection, helmet_mode: bool) -> tuple[int, int, int]:
        if helmet_mode:
            return (
                (0, 200, 0)
                if det.helmet_status == HelmetStatus.SAFE
                else (0, 0, 255)
            )
        return cls._LINE_COLORS.get(det.zone_color, cls._LINE_COLORS["safe"])

    @classmethod
    def _annotate(
        cls,
        frame: np.ndarray,
        detections: list[WorkerDetection],
        line_detector: LineCrossingDetector | None,
        helmet_mode: bool,
    ) -> np.ndarray:
        canvas = frame.copy()

        if line_detector is not None:
            for name, p1, p2 in line_detector.segments():
                color = cls._LINE_COLORS.get(name, (255, 255, 255))
                cv2.line(canvas, p1, p2, color, 2)
                label_x = min(p1[0], p2[0])
                label_y = min(p1[1], p2[1])
                cv2.putText(
                    canvas,
                    f"{name.upper()} LINE",
                    (label_x, max(label_y - 8, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = cls._bbox_color(det, helmet_mode)
            if helmet_mode:
                label = f"ID:{det.worker_id} {det.helmet_status.value}"
            else:
                label = f"ID:{det.worker_id}"
                if det.zone_color not in ("safe", "green"):
                    label += f" [{det.zone_color.upper()}]"
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.circle(canvas, (int(det.foot_x), int(det.foot_y)), 5, color, -1)
            cv2.putText(
                canvas,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )
        return canvas
