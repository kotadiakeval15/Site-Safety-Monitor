"""YOLOv8 person and helmet detection.

Detection rules are preserved from the original inference-service engine:
person = COCO class 0 at the configured confidence; helmet detection uses an
optional second model with label heuristics (skip ``no``/``without`` labels).
"""

from __future__ import annotations

import logging

import numpy as np
import supervision as sv
from ultralytics import YOLO

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0


class PersonHelmetDetector:
    """Wraps the person model and the optional helmet model."""

    def __init__(
        self,
        person_model_path: str = "yolov8n.pt",
        helmet_model_path: str | None = None,
        confidence: float = 0.45,
        device: str = "cpu",
    ) -> None:
        self._confidence = confidence
        self._device = device
        self._person_model = YOLO(person_model_path)
        self._helmet_model = YOLO(helmet_model_path) if helmet_model_path else None
        logger.info(
            "Detector loaded person=%s helmet=%s device=%s",
            person_model_path,
            helmet_model_path,
            device,
        )

    @property
    def has_helmet_model(self) -> bool:
        return self._helmet_model is not None

    def detect_persons(self, frame: np.ndarray) -> sv.Detections:
        results = self._person_model.predict(
            source=frame,
            conf=self._confidence,
            classes=[PERSON_CLASS_ID],
            device=self._device,
            verbose=False,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return sv.Detections.empty()
        result = results[0]
        return sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int),
        )

    def detect_helmets(self, frame: np.ndarray) -> list[tuple[float, float, float]]:
        """Return helmet centroids as ``(cx, cy, confidence)`` tuples."""

        if self._helmet_model is None:
            return []
        results = self._helmet_model.predict(
            source=frame,
            conf=self._confidence,
            device=self._device,
            verbose=False,
        )
        if not results or results[0].boxes is None:
            return []
        centroids: list[tuple[float, float, float]] = []
        names = results[0].names or {}
        for box in results[0].boxes:
            cls_id = int(box.cls.item())
            label = names.get(cls_id, str(cls_id)).lower()
            if "no" in label or "without" in label:
                continue
            if any(h in label for h in ("helmet", "hardhat", "head")) or cls_id != PERSON_CLASS_ID:
                xyxy = box.xyxy.cpu().numpy()[0]
                cx = (xyxy[0] + xyxy[2]) / 2
                cy = (xyxy[1] + xyxy[3]) / 2
                centroids.append((float(cx), float(cy), float(box.conf.item())))
        return centroids
