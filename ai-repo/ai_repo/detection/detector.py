"""YOLOv8 person and helmet detection.

Person = COCO class 0. Helmet compliance uses a dedicated YOLO model whose
classes are mapped as:
  helmet / industrial helmet / safety helmet -> compliant (safe)
  head / no helmet / without helmet         -> violation
  person                                   -> ignored for helmet association
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import supervision as sv
from ultralytics import YOLO

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0

_IGNORE_LABEL_FRAGMENTS = ("person",)
_COMPLIANT_LABEL_FRAGMENTS = (
    "helmet",
    "hardhat",
    "hard_hat",
    "hard-hat",
    "safety_helmet",
    "industrial_helmet",
    "safety helmet",
    "industrial helmet",
)
_VIOLATION_LABEL_FRAGMENTS = (
    "head",
    "no_helmet",
    "nohelmet",
    "without_helmet",
    "without helmet",
    "no helmet",
)


@dataclass(frozen=True)
class HelmetDetection:
    """One helmet-model detection associated with a person's head region."""

    cx: float
    cy: float
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    is_compliant: bool


class PersonHelmetDetector:
    """Wraps the person model and the optional helmet model."""

    def __init__(
        self,
        person_model_path: str = "yolov8n.pt",
        helmet_model_path: str | None = None,
        confidence: float = 0.45,
        device: str = "cpu",
    ) -> None:
        self._helmet_confidence = confidence
        self._person_confidence = max(0.25, confidence - 0.15)
        self._device = device
        self._person_model = YOLO(person_model_path)
        self._helmet_model = YOLO(helmet_model_path) if helmet_model_path else None
        if self._helmet_model is not None:
            logger.info(
                "Helmet model loaded from %s classes=%s",
                helmet_model_path,
                self._helmet_model.names,
            )
        logger.info(
            "Detector loaded person=%s helmet=%s device=%s person_conf=%.2f",
            person_model_path,
            helmet_model_path,
            device,
            self._person_confidence,
        )

    @property
    def has_helmet_model(self) -> bool:
        return self._helmet_model is not None

    def detect_persons(self, frame: np.ndarray) -> sv.Detections:
        results = self._person_model.predict(
            source=frame,
            conf=self._person_confidence,
            classes=[PERSON_CLASS_ID],
            device=self._device,
            verbose=False,
            iou=0.5,
            max_det=100,
            imgsz=640,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return sv.Detections.empty()
        result = results[0]
        return sv.Detections(
            xyxy=result.boxes.xyxy.cpu().numpy(),
            confidence=result.boxes.conf.cpu().numpy(),
            class_id=result.boxes.cls.cpu().numpy().astype(int),
        )

    @classmethod
    def _helmet_label_kind(cls, label: str) -> str | None:
        """Return ``compliant``, ``violation``, or ``None`` (ignore)."""

        normalized = label.lower().replace("-", "_").strip()
        if any(fragment in normalized for fragment in _IGNORE_LABEL_FRAGMENTS):
            return None
        if normalized == "head" or any(
            fragment.replace(" ", "_") in normalized for fragment in _VIOLATION_LABEL_FRAGMENTS
        ):
            return "violation"
        if "without" in normalized and "helmet" in normalized:
            return "violation"
        if "no" in normalized and "helmet" in normalized:
            return "violation"
        if any(fragment.replace(" ", "_") in normalized for fragment in _COMPLIANT_LABEL_FRAGMENTS):
            return "compliant"
        if normalized == "helmet" or normalized.endswith("_helmet"):
            return "compliant"
        return None

    def detect_helmets(self, frame: np.ndarray) -> list[HelmetDetection]:
        """Return fresh helmet-model detections for the current frame."""

        if self._helmet_model is None:
            return []
        results = self._helmet_model.predict(
            source=frame,
            conf=self._helmet_confidence,
            device=self._device,
            verbose=False,
            max_det=100,
            imgsz=640,
        )
        if not results or results[0].boxes is None:
            return []
        detections: list[HelmetDetection] = []
        names = results[0].names or {}
        for box in results[0].boxes:
            cls_id = int(box.cls.item())
            label = str(names.get(cls_id, str(cls_id)))
            kind = self._helmet_label_kind(label)
            if kind is None:
                continue
            xyxy = box.xyxy.cpu().numpy()[0]
            detections.append(
                HelmetDetection(
                    cx=float((xyxy[0] + xyxy[2]) / 2),
                    cy=float((xyxy[1] + xyxy[3]) / 2),
                    conf=float(box.conf.item()),
                    x1=float(xyxy[0]),
                    y1=float(xyxy[1]),
                    x2=float(xyxy[2]),
                    y2=float(xyxy[3]),
                    label=label.lower(),
                    is_compliant=kind == "compliant",
                )
            )
        return detections
