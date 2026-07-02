#!/usr/bin/env python3
"""
Construction Site Safety Anomaly Detection – Multi-Level Restricted Area Monitoring POC.

Real-time computer vision application that monitors construction-site safety zones,
detects persons with YOLOv8, tracks them with ByteTrack, and escalates alerts
through three horizontal boundary lines: GREEN (safe), YELLOW (warning), RED (restricted).

Example:
    py safety_monitor.py --input-dir input_videos
    py safety_monitor.py --source input_videos/lobby_demo1.mp4
    py safety_monitor.py --source 0
"""

from __future__ import annotations

import argparse
import atexit
import csv
import logging
import shutil
import signal
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Final, Optional, Sequence

import cv2
import numpy as np
import pandas as pd
import supervision as sv
from scipy.io import wavfile
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Global configuration variables
# ---------------------------------------------------------------------------

CAMERA_SOURCE: str | int = 0
MODEL_PATH: str = "yolov8n.pt"
CONFIDENCE_THRESHOLD: float = 0.45
FRAME_SKIP: int = 1
WARNING_COOLDOWN_SECONDS: float = 10.0
DISPLAY_FPS: bool = True
OUTPUT_VIDEO_ENABLED: bool = True
OUTPUT_VIDEO_DIRECTORY: str = "output_videos"
OUTPUT_VIDEO_FILENAME: str = "safety_monitor_{source}_{timestamp}_UTC.mp4"
INPUT_VIDEO_DIRECTORY: str = "input_videos"
VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v", ".webm"}
)

PERSON_CLASS_ID: Final[int] = 0
LOG_DIRECTORY: Final[str] = "logs"
EVENT_LOG_FILENAME: Final[str] = "safety_events.csv"

# Perspective floor quadrilateral corners (x_ratio, y_ratio):
# far-left, far-right, near-right, near-left — defines the walkable floor plane.
FLOOR_FAR_LEFT: Final[tuple[float, float]] = (0.28, 0.38)
FLOOR_FAR_RIGHT: Final[tuple[float, float]] = (0.72, 0.38)
FLOOR_NEAR_RIGHT: Final[tuple[float, float]] = (0.96, 0.96)
FLOOR_NEAR_LEFT: Final[tuple[float, float]] = (0.04, 0.96)

# Equal depth splits along floor Z-axis (far→near): RED | YELLOW | GREEN
ZONE_DEPTH_SPLIT_1: Final[float] = 1.0 / 3.0
ZONE_DEPTH_SPLIT_2: Final[float] = 2.0 / 3.0

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations and shared data models
# ---------------------------------------------------------------------------


class ZoneSeverity(str, Enum):
    """Severity levels assigned to safety zones."""

    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SystemStatus(str, Enum):
    """Overall monitoring system state derived from all tracked persons."""

    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    """CSV event log event types."""

    SAFE_ENTRY = "SAFE_ENTRY"
    SAFE_EXIT = "SAFE_EXIT"
    WARNING_ENTRY = "WARNING_ENTRY"
    WARNING_EXIT = "WARNING_EXIT"
    RESTRICTED_ENTRY = "RESTRICTED_ENTRY"
    RESTRICTED_EXIT = "RESTRICTED_EXIT"


class PersonZoneState(str, Enum):
    """Per-person zone occupancy state."""

    OUTSIDE = "OUTSIDE"
    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Point:
    """2D point with integer pixel coordinates."""

    x: int
    y: int

    def as_tuple(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass(frozen=True)
class DetectionResult:
    """Single tracked person detection."""

    tracker_id: int
    confidence: float
    bbox: tuple[int, int, int, int]
    centroid: Point
    zone_state: PersonZoneState


@dataclass
class MonitoringSnapshot:
    """Aggregated frame-level monitoring metrics."""

    detections: list[DetectionResult] = field(default_factory=list)
    total_persons: int = 0
    outside_count: int = 0
    safe_count: int = 0
    warning_count: int = 0
    restricted_count: int = 0
    system_status: SystemStatus = SystemStatus.SAFE
    fps: float = 0.0
    status_message: str = ""
    display_fps: bool = True


@dataclass(frozen=True)
class SafetyEvent:
    """Structured safety event for CSV logging."""

    timestamp_utc: str
    event_type: EventType
    person_id: int
    zone_name: str
    zone_severity: ZoneSeverity
    confidence: float
    centroid_x: int
    centroid_y: int


@dataclass
class AppConfig:
    """Application configuration container."""

    camera_source: str | int = CAMERA_SOURCE
    model_path: str = MODEL_PATH
    confidence_threshold: float = CONFIDENCE_THRESHOLD
    frame_skip: int = FRAME_SKIP
    warning_cooldown_seconds: float = WARNING_COOLDOWN_SECONDS
    display_fps: bool = DISPLAY_FPS
    output_video_enabled: bool = OUTPUT_VIDEO_ENABLED
    output_video_directory: str = OUTPUT_VIDEO_DIRECTORY
    output_video_filename: str = OUTPUT_VIDEO_FILENAME
    device: str = "cpu"
    floor_far_left: tuple[float, float] = FLOOR_FAR_LEFT
    floor_far_right: tuple[float, float] = FLOOR_FAR_RIGHT
    floor_near_right: tuple[float, float] = FLOOR_NEAR_RIGHT
    floor_near_left: tuple[float, float] = FLOOR_NEAR_LEFT
    auto_detect_floor: bool = True
    input_video_directory: str = INPUT_VIDEO_DIRECTORY
    log_directory: str = LOG_DIRECTORY
    event_log_filename: str = EVENT_LOG_FILENAME
    reference_width: int = 1280
    reference_height: int = 720
    source_label: str = "live"

    def resolve_output_video_path(self) -> Path:
        """Build UTC timestamped output video path."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = self.output_video_filename.format(
            source=self.source_label,
            timestamp=timestamp,
        )
        return Path(self.output_video_directory) / filename

    def resolve_event_log_path(self) -> Path:
        """Build event log CSV path."""
        return Path(self.log_directory) / self.event_log_filename


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def configure_logging(log_directory: str = LOG_DIRECTORY) -> None:
    """Configure console and rotating file logging."""
    log_path = Path(log_directory)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "safety_monitor.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S UTC",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
        force=True,
    )
    logging.Formatter.converter = time.gmtime
    logger.info("Logging initialized. Log file: %s", log_file)


# ---------------------------------------------------------------------------
# Video source management
# ---------------------------------------------------------------------------


class VideoSourceManager:
    """Manages video capture from webcam, RTSP, or file sources."""

    def __init__(self, source: str | int) -> None:
        self._source = self._parse_source(source)
        self._capture: Optional[cv2.VideoCapture] = None

    @staticmethod
    def _parse_source(source: str | int) -> str | int:
        if isinstance(source, int):
            return source
        if isinstance(source, str) and source.isdigit():
            return int(source)
        return source

    def open(self) -> None:
        """Open the configured video source."""
        self._capture = cv2.VideoCapture(self._source)
        if not self._capture.isOpened():
            raise RuntimeError(f"Unable to open video source: {self._source}")
        logger.info("Video source opened: %s", self._source)

    @property
    def is_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        """Read the next frame."""
        if self._capture is None:
            return False, None
        success, frame = self._capture.read()
        if not success:
            return False, None
        return True, frame

    def get_frame_size(self) -> tuple[int, int]:
        """Return (width, height) of the video stream."""
        if self._capture is None:
            raise RuntimeError("Video capture is not open.")
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height

    def get_fps(self) -> float:
        if self._capture is None:
            return 30.0
        fps = float(self._capture.get(cv2.CAP_PROP_FPS))
        return fps if fps > 0 else 30.0

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.info("Video source released.")


# ---------------------------------------------------------------------------
# Person detection
# ---------------------------------------------------------------------------


class YOLOPersonDetector:
    """YOLOv8-based person detector supporting CPU and GPU execution."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float,
        device: str = "cpu",
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._device = device
        try:
            self._model = YOLO(model_path)
            logger.info("Loaded YOLO model from %s on device %s", model_path, device)
        except Exception as exc:
            logger.exception("Failed to load YOLO model.")
            raise RuntimeError(f"Could not load model '{model_path}'.") from exc

    def detect(self, frame: np.ndarray) -> sv.Detections:
        """Detect persons in a frame and return supervision Detections."""
        results = self._model.predict(
            source=frame,
            conf=self._confidence_threshold,
            classes=[PERSON_CLASS_ID],
            device=self._device,
            verbose=False,
        )
        if not results:
            return sv.Detections.empty()

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return sv.Detections.empty()

        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)

        return sv.Detections(
            xyxy=boxes,
            confidence=confidences,
            class_id=class_ids,
        )


# ---------------------------------------------------------------------------
# Person tracking
# ---------------------------------------------------------------------------


class PersonTracker:
    """Lightweight ByteTrack wrapper for stable temporary person IDs."""

    def __init__(self) -> None:
        self._tracker = sv.ByteTrack()

    def update(self, detections: sv.Detections) -> sv.Detections:
        """Apply tracking to detections."""
        if len(detections) == 0:
            return detections
        return self._tracker.update_with_detections(detections)

    @staticmethod
    def compute_centroid(bbox: tuple[int, int, int, int]) -> Point:
        x1, y1, x2, y2 = bbox
        return Point(x=(x1 + x2) // 2, y=(y1 + y2) // 2)

    @staticmethod
    def compute_foot_point(bbox: tuple[int, int, int, int]) -> Point:
        """Bottom-center of bbox — best reference for floor line crossing."""
        x1, _y1, x2, y2 = bbox
        return Point(x=(x1 + x2) // 2, y=y2)


# ---------------------------------------------------------------------------
# Zone management
# ---------------------------------------------------------------------------


class FloorZoneManager:
    """
    Perspective floor plane with three equal depth (Z-axis) zones.

    The floor is a trapezoid in the image. Depth v=0 is the far hallway end,
    v=1 is near the camera. Boundaries are lines across the floor (not screen-Y bands).
    Sequence far→near when walking toward camera: RED → YELLOW → GREEN.
    """

    def __init__(
        self,
        far_left: tuple[float, float],
        far_right: tuple[float, float],
        near_right: tuple[float, float],
        near_left: tuple[float, float],
        auto_detect_floor: bool = True,
    ) -> None:
        self._corner_ratios = (far_left, far_right, near_right, near_left)
        self._auto_detect_floor = auto_detect_floor
        self._floor_quad = np.zeros((4, 2), dtype=np.float32)
        self._homography_to_floor: Optional[np.ndarray] = None
        self._frame_width = 0
        self._frame_height = 0
        self._initialized = False

    def initialize_for_frame(
        self,
        frame_width: int,
        frame_height: int,
        frame: Optional[np.ndarray] = None,
    ) -> None:
        if self._initialized and self._frame_height == frame_height:
            return

        self._frame_width = frame_width
        self._frame_height = frame_height
        base_quad = self._build_quad_from_ratios(frame_width, frame_height)

        if frame is not None and self._auto_detect_floor:
            detected = self._detect_floor_quad(frame, base_quad)
            self._floor_quad = detected
        else:
            self._floor_quad = base_quad

        self._homography_to_floor = self._compute_image_to_floor_homography()
        self._initialized = True
        logger.info(
            "Perspective floor initialized %dx%d | corners=%s",
            frame_width,
            frame_height,
            self._floor_quad.astype(int).tolist(),
        )

    @property
    def floor_quad(self) -> np.ndarray:
        return self._floor_quad.astype(int)

    def _build_quad_from_ratios(self, width: int, height: int) -> np.ndarray:
        fl, fr, nr, nl = self._corner_ratios
        return np.float32(
            [
                [fl[0] * width, fl[1] * height],
                [fr[0] * width, fr[1] * height],
                [nr[0] * width, nr[1] * height],
                [nl[0] * width, nl[1] * height],
            ]
        )

    def _detect_floor_quad(
        self,
        frame: np.ndarray,
        fallback: np.ndarray,
    ) -> np.ndarray:
        """Detect bright walkable floor tiles and fit a perspective quadrilateral."""
        height, width = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 90), (180, 90, 255))
        mask[: int(height * 0.30), :] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return fallback

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < width * height * 0.08:
            return fallback

        hull = cv2.convexHull(largest)
        epsilon = 0.02 * cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(hull, epsilon, True)
        if len(approx) < 4:
            return fallback

        points = approx.reshape(-1, 2).astype(np.float32)
        return self._order_floor_quad(points, fallback)

    @staticmethod
    def _order_floor_quad(points: np.ndarray, fallback: np.ndarray) -> np.ndarray:
        """Order points as far-left, far-right, near-right, near-left."""
        if len(points) < 4:
            return fallback

        sorted_by_y = points[np.argsort(points[:, 1])]
        far_pair = sorted_by_y[:2]
        near_pair = sorted_by_y[-2:]
        far_left = far_pair[np.argmin(far_pair[:, 0])]
        far_right = far_pair[np.argmax(far_pair[:, 0])]
        near_left = near_pair[np.argmin(near_pair[:, 0])]
        near_right = near_pair[np.argmax(near_pair[:, 0])]
        return np.float32([far_left, far_right, near_right, near_left])

    def _compute_image_to_floor_homography(self) -> np.ndarray:
        unit_square = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
        floor_to_image = cv2.getPerspectiveTransform(unit_square, self._floor_quad)
        return cv2.invert(floor_to_image)[1]

    def _image_to_floor_uv(self, point: Point) -> Optional[tuple[float, float]]:
        if self._homography_to_floor is None:
            return None
        vector = np.array([point.x, point.y, 1.0], dtype=np.float64)
        mapped = self._homography_to_floor @ vector
        if abs(mapped[2]) < 1e-6:
            return None
        u = float(mapped[0] / mapped[2])
        v = float(mapped[1] / mapped[2])
        return u, v

    def classify_point(self, point: Point) -> PersonZoneState:
        """
        Classify using depth on the perspective floor plane (Z-axis).

        v = 0 far end, v = 1 near camera.
        Equal thirds: CRITICAL (red) | WARNING (yellow) | SAFE (green).
        """
        if cv2.pointPolygonTest(self._floor_quad, point.as_tuple(), False) < 0:
            return PersonZoneState.OUTSIDE

        uv = self._image_to_floor_uv(point)
        if uv is None:
            return PersonZoneState.OUTSIDE

        _u, depth = uv
        if depth < 0.0 or depth > 1.0:
            return PersonZoneState.OUTSIDE

        if depth < ZONE_DEPTH_SPLIT_1:
            return PersonZoneState.CRITICAL
        if depth < ZONE_DEPTH_SPLIT_2:
            return PersonZoneState.WARNING
        return PersonZoneState.SAFE

    def depth_boundary_segments(self) -> list[tuple[np.ndarray, str, tuple[int, int, int]]]:
        """Return floor boundary segments at 1/3 and 2/3 depth for rendering."""
        return [
            (self._segment_at_depth(ZONE_DEPTH_SPLIT_1), "RED LINE", (0, 0, 255)),
            (self._segment_at_depth(ZONE_DEPTH_SPLIT_2), "YELLOW LINE", (0, 220, 255)),
        ]

    def zone_polygons(self) -> list[tuple[np.ndarray, str, tuple[int, int, int], float]]:
        """Return perspective zone polygons far→near for overlay rendering."""
        return [
            (
                self._band_polygon(0.0, ZONE_DEPTH_SPLIT_1),
                "RESTRICTED ZONE",
                (0, 0, 255),
                0.16,
            ),
            (
                self._band_polygon(ZONE_DEPTH_SPLIT_1, ZONE_DEPTH_SPLIT_2),
                "WARNING ZONE",
                (0, 220, 255),
                0.14,
            ),
            (
                self._band_polygon(ZONE_DEPTH_SPLIT_2, 1.0),
                "SAFE ZONE",
                (0, 180, 0),
                0.12,
            ),
        ]

    def _edge_at_depth(self, depth: float) -> tuple[np.ndarray, np.ndarray]:
        fl, fr, nr, nl = self._floor_quad
        left = (1.0 - depth) * fl + depth * nl
        right = (1.0 - depth) * fr + depth * nr
        return left, right

    def _segment_at_depth(self, depth: float) -> np.ndarray:
        left, right = self._edge_at_depth(depth)
        return np.array([left, right], dtype=np.int32)

    def _band_polygon(self, depth_start: float, depth_end: float) -> np.ndarray:
        l0, r0 = self._edge_at_depth(depth_start)
        l1, r1 = self._edge_at_depth(depth_end)
        return np.array([l0, r0, r1, l1], dtype=np.int32)

    def near_boundary_segment(self) -> np.ndarray:
        """Near-camera (green) floor boundary segment."""
        return self._segment_at_depth(1.0)

    def reset(self) -> None:
        self._initialized = False


# ---------------------------------------------------------------------------
# Session audio track (synthesized alert sounds for video export)
# ---------------------------------------------------------------------------


class SessionAudioTrack:
    """Records alert timing and synthesizes an audio track for the output video."""

    SAMPLE_RATE: Final[int] = 44100
    WARNING_FREQUENCY_HZ: Final[int] = 880
    WARNING_DURATION_MS: Final[int] = 250
    CRITICAL_FREQUENCY_HZ: Final[int] = 1200
    CRITICAL_BEEP_MS: Final[int] = 180
    CRITICAL_GAP_MS: Final[int] = 120

    def __init__(self, fps: float) -> None:
        self._fps = fps if fps > 0 else 30.0
        self._frame_index = 0
        self._warning_frames: list[int] = []
        self._critical_intervals: list[tuple[int, int]] = []
        self._critical_active = False
        self._critical_start_frame: Optional[int] = None

    def advance_frame(self) -> None:
        """Advance the frame clock by one recorded video frame."""
        self._frame_index += 1

    def register_warning_beep(self) -> None:
        """Record a warning beep at the current frame."""
        self._warning_frames.append(self._frame_index)

    def set_critical_active(self, active: bool) -> None:
        """Record critical alarm start/stop aligned to the current frame."""
        if active and not self._critical_active:
            self._critical_start_frame = self._frame_index
            self._critical_active = True
        elif not active and self._critical_active:
            if self._critical_start_frame is not None:
                self._critical_intervals.append(
                    (self._critical_start_frame, self._frame_index)
                )
            self._critical_active = False
            self._critical_start_frame = None

    def finalize(self, total_frames: int) -> None:
        """Close any open critical interval at end of recording."""
        if self._critical_active and self._critical_start_frame is not None:
            self._critical_intervals.append((self._critical_start_frame, total_frames))
            self._critical_active = False
            self._critical_start_frame = None

    def synthesize(self, total_frames: int) -> np.ndarray:
        """Build a mono int16 PCM track matching alert events in the session."""
        duration_seconds = total_frames / self._fps
        sample_count = int(duration_seconds * self.SAMPLE_RATE) + self.SAMPLE_RATE
        audio = np.zeros(sample_count, dtype=np.float64)

        for frame_idx in self._warning_frames:
            start_sample = int((frame_idx / self._fps) * self.SAMPLE_RATE)
            self._mix_tone(
                audio,
                start_sample,
                self.WARNING_DURATION_MS,
                self.WARNING_FREQUENCY_HZ,
                amplitude=0.35,
            )

        for start_frame, end_frame in self._critical_intervals:
            cursor_seconds = start_frame / self._fps
            end_seconds = end_frame / self._fps
            while cursor_seconds < end_seconds:
                start_sample = int(cursor_seconds * self.SAMPLE_RATE)
                self._mix_tone(
                    audio,
                    start_sample,
                    self.CRITICAL_BEEP_MS,
                    self.CRITICAL_FREQUENCY_HZ,
                    amplitude=0.4,
                )
                cursor_seconds += (self.CRITICAL_BEEP_MS + self.CRITICAL_GAP_MS) / 1000.0

        peak = float(np.max(np.abs(audio)))
        if peak > 1.0:
            audio /= peak
        return (audio * 32767.0).astype(np.int16)

    def _mix_tone(
        self,
        audio: np.ndarray,
        start_sample: int,
        duration_ms: int,
        frequency_hz: int,
        amplitude: float,
    ) -> None:
        sample_count = int(self.SAMPLE_RATE * duration_ms / 1000)
        timeline = np.arange(sample_count) / self.SAMPLE_RATE
        fade = max(1, int(0.01 * self.SAMPLE_RATE))
        envelope = np.ones(sample_count)
        envelope[:fade] = np.linspace(0.0, 1.0, fade)
        envelope[-fade:] = np.linspace(1.0, 0.0, fade)
        tone = amplitude * envelope * np.sin(2.0 * np.pi * frequency_hz * timeline)
        end_sample = min(start_sample + sample_count, len(audio))
        clip_length = end_sample - start_sample
        audio[start_sample:end_sample] += tone[:clip_length]


# ---------------------------------------------------------------------------
# Alert management
# ---------------------------------------------------------------------------


class AlertManager:
    """Handles warning beeps and continuous critical alarm playback."""

    def __init__(self, audio_track: Optional[SessionAudioTrack] = None) -> None:
        self._alarm_stop_event = threading.Event()
        self._alarm_thread: Optional[threading.Thread] = None
        self._platform = sys.platform
        self._audio_track = audio_track
        self._critical_alarm_active = False

    def attach_audio_track(self, audio_track: SessionAudioTrack) -> None:
        """Connect session audio recording for exported video alerts."""
        self._audio_track = audio_track

    def play_warning_beep(self) -> None:
        """Play a short one-time warning beep."""
        if self._audio_track is not None:
            self._audio_track.register_warning_beep()
        threading.Thread(target=self._warning_beep, daemon=True).start()

    def update_critical_alarm(self, restricted_count: int) -> None:
        """Start or stop continuous alarm based on restricted zone occupancy."""
        if restricted_count > 0:
            if not self._critical_alarm_active:
                if self._audio_track is not None:
                    self._audio_track.set_critical_active(True)
                self._critical_alarm_active = True
            self._start_critical_alarm()
        else:
            if self._critical_alarm_active:
                if self._audio_track is not None:
                    self._audio_track.set_critical_active(False)
                self._critical_alarm_active = False
            self._stop_critical_alarm()

    def shutdown(self) -> None:
        """Ensure alarm thread is stopped on application exit."""
        if self._critical_alarm_active and self._audio_track is not None:
            self._audio_track.set_critical_active(False)
            self._critical_alarm_active = False
        self._stop_critical_alarm()

    def _warning_beep(self) -> None:
        try:
            if self._platform.startswith("win"):
                import winsound

                winsound.Beep(880, 250)
            else:
                print("\a", end="", flush=True)
        except Exception:
            logger.exception("Failed to play warning beep.")

    def _alarm_loop(self) -> None:
        while not self._alarm_stop_event.is_set():
            try:
                if self._platform.startswith("win"):
                    import winsound

                    winsound.Beep(1200, 180)
                else:
                    print("\a", end="", flush=True)
            except Exception:
                logger.exception("Critical alarm playback error.")
            self._alarm_stop_event.wait(0.12)

    def _start_critical_alarm(self) -> None:
        if self._alarm_thread and self._alarm_thread.is_alive():
            return
        self._alarm_stop_event.clear()
        self._alarm_thread = threading.Thread(target=self._alarm_loop, daemon=True)
        self._alarm_thread.start()
        logger.critical("Critical alarm activated.")

    def _stop_critical_alarm(self) -> None:
        if self._alarm_thread is None:
            return
        self._alarm_stop_event.set()
        if self._alarm_thread.is_alive():
            self._alarm_thread.join(timeout=1.0)
        self._alarm_thread = None
        logger.info("Critical alarm deactivated.")


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------


class EventLogger:
    """Persists safety events to CSV format."""

    CSV_HEADERS: Final[list[str]] = [
        "UTC Timestamp",
        "Event Type",
        "Person ID",
        "Zone Name",
        "Zone Severity",
        "Confidence Score",
        "Centroid X",
        "Centroid Y",
    ]

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    def _ensure_header(self) -> None:
        if not self._log_path.exists():
            with self._log_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(self.CSV_HEADERS)
            logger.info("Created event log: %s", self._log_path)

    def log_event(self, event: SafetyEvent) -> None:
        row = [
            event.timestamp_utc,
            event.event_type.value,
            event.person_id,
            event.zone_name,
            event.zone_severity.value,
            f"{event.confidence:.4f}",
            event.centroid_x,
            event.centroid_y,
        ]
        with self._log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(row)

    def summary_dataframe(self) -> pd.DataFrame:
        """Load events as a pandas DataFrame for optional analysis."""
        if not self._log_path.exists():
            return pd.DataFrame(columns=self.CSV_HEADERS)
        return pd.read_csv(self._log_path)


# ---------------------------------------------------------------------------
# Status banner
# ---------------------------------------------------------------------------


class StatusBanner:
    """Thread-safe overlay message with priority-based updates."""

    PRIORITY_CAUTION: Final[int] = 10
    PRIORITY_WARNING: Final[int] = 20
    PRIORITY_CRITICAL: Final[int] = 30

    def __init__(self) -> None:
        self._message = ""
        self._priority = 0
        self._lock = threading.Lock()

    def publish(self, message: str, priority: int) -> None:
        with self._lock:
            if priority >= self._priority:
                self._message = message
                self._priority = priority

    def read(self) -> str:
        with self._lock:
            return self._message

    def reset(self) -> None:
        with self._lock:
            self._message = ""
            self._priority = 0


# ---------------------------------------------------------------------------
# Zone monitors (Single Responsibility)
# ---------------------------------------------------------------------------


class ZoneMonitor(ABC):
    """Abstract zone transition monitor."""

    @abstractmethod
    def evaluate(
        self,
        person_id: int,
        current_state: PersonZoneState,
        confidence: float,
        centroid: Point,
    ) -> None:
        """Evaluate zone transitions for a tracked person."""


class SafeZoneMonitor(ZoneMonitor):
    """Monitors green-line crossing into safe zone (text alert only)."""

    def __init__(
        self,
        event_logger: EventLogger,
        status_banner: StatusBanner,
        cooldown_seconds: float,
    ) -> None:
        self._event_logger = event_logger
        self._status_banner = status_banner
        self._cooldown_seconds = cooldown_seconds
        self._previous_states: dict[int, PersonZoneState] = {}
        self._last_notice_time: dict[int, float] = {}

    def evaluate(
        self,
        person_id: int,
        current_state: PersonZoneState,
        confidence: float,
        centroid: Point,
    ) -> None:
        previous = self._previous_states.get(person_id, PersonZoneState.OUTSIDE)

        if (
            previous == PersonZoneState.WARNING
            and current_state == PersonZoneState.SAFE
        ):
            now = time.monotonic()
            last = self._last_notice_time.get(person_id, 0.0)
            if now - last >= self._cooldown_seconds:
                self._last_notice_time[person_id] = now
                self._status_banner.publish(
                    "SAFE: You Are in the Safe Zone",
                    StatusBanner.PRIORITY_CAUTION,
                )
                self._event_logger.log_event(
                    SafetyEvent(
                        timestamp_utc=_utc_now_iso(),
                        event_type=EventType.SAFE_ENTRY,
                        person_id=person_id,
                        zone_name="SAFE ZONE",
                        zone_severity=ZoneSeverity.SAFE,
                        confidence=confidence,
                        centroid_x=centroid.x,
                        centroid_y=centroid.y,
                    )
                )
                logger.info("Person %s crossed GREEN line into SAFE zone.", person_id)

        elif (
            previous == PersonZoneState.SAFE
            and current_state == PersonZoneState.WARNING
        ):
            self._event_logger.log_event(
                SafetyEvent(
                    timestamp_utc=_utc_now_iso(),
                    event_type=EventType.SAFE_EXIT,
                    person_id=person_id,
                    zone_name="SAFE ZONE",
                    zone_severity=ZoneSeverity.SAFE,
                    confidence=confidence,
                    centroid_x=centroid.x,
                    centroid_y=centroid.y,
                )
            )
            logger.info("Person %s exited SAFE zone.", person_id)

        self._previous_states[person_id] = current_state

    def prune_stale_ids(self, active_ids: set[int]) -> None:
        stale = set(self._previous_states) - active_ids
        for person_id in stale:
            self._previous_states.pop(person_id, None)
            self._last_notice_time.pop(person_id, None)

    def reset(self) -> None:
        self._previous_states.clear()
        self._last_notice_time.clear()


class WarningZoneMonitor(ZoneMonitor):
    """Monitors yellow-line crossing into warning zone (single beep)."""

    def __init__(
        self,
        alert_manager: AlertManager,
        event_logger: EventLogger,
        status_banner: StatusBanner,
        cooldown_seconds: float,
    ) -> None:
        self._alert_manager = alert_manager
        self._event_logger = event_logger
        self._status_banner = status_banner
        self._cooldown_seconds = cooldown_seconds
        self._previous_states: dict[int, PersonZoneState] = {}
        self._last_warning_time: dict[int, float] = {}

    def evaluate(
        self,
        person_id: int,
        current_state: PersonZoneState,
        confidence: float,
        centroid: Point,
    ) -> None:
        previous = self._previous_states.get(person_id, PersonZoneState.OUTSIDE)

        if (
            previous == PersonZoneState.CRITICAL
            and current_state == PersonZoneState.WARNING
        ):
            now = time.monotonic()
            last = self._last_warning_time.get(person_id, 0.0)
            if now - last >= self._cooldown_seconds:
                self._last_warning_time[person_id] = now
                self._status_banner.publish(
                    "WARNING: Do Not Enter Restricted Zone",
                    StatusBanner.PRIORITY_WARNING,
                )
                self._alert_manager.play_warning_beep()
                self._event_logger.log_event(
                    SafetyEvent(
                        timestamp_utc=_utc_now_iso(),
                        event_type=EventType.WARNING_ENTRY,
                        person_id=person_id,
                        zone_name="WARNING ZONE",
                        zone_severity=ZoneSeverity.WARNING,
                        confidence=confidence,
                        centroid_x=centroid.x,
                        centroid_y=centroid.y,
                    )
                )
                logger.warning("Person %s crossed YELLOW line into WARNING zone.", person_id)

        elif (
            previous == PersonZoneState.WARNING
            and current_state in (PersonZoneState.CRITICAL, PersonZoneState.SAFE)
        ):
            self._event_logger.log_event(
                SafetyEvent(
                    timestamp_utc=_utc_now_iso(),
                    event_type=EventType.WARNING_EXIT,
                    person_id=person_id,
                    zone_name="WARNING ZONE",
                    zone_severity=ZoneSeverity.WARNING,
                    confidence=confidence,
                    centroid_x=centroid.x,
                    centroid_y=centroid.y,
                )
            )
            logger.info("Person %s exited WARNING zone.", person_id)

        self._previous_states[person_id] = current_state

    def prune_stale_ids(self, active_ids: set[int]) -> None:
        """Remove state for persons no longer tracked."""
        stale = set(self._previous_states) - active_ids
        for person_id in stale:
            self._previous_states.pop(person_id, None)
            self._last_warning_time.pop(person_id, None)

    def reset(self) -> None:
        self._previous_states.clear()
        self._last_warning_time.clear()


class RestrictedZoneMonitor(ZoneMonitor):
    """Monitors restricted zone entry/exit and drives critical alarm state."""

    def __init__(
        self,
        alert_manager: AlertManager,
        event_logger: EventLogger,
        status_banner: StatusBanner,
    ) -> None:
        self._alert_manager = alert_manager
        self._event_logger = event_logger
        self._status_banner = status_banner
        self._previous_states: dict[int, PersonZoneState] = {}

    def evaluate(
        self,
        person_id: int,
        current_state: PersonZoneState,
        confidence: float,
        centroid: Point,
    ) -> None:
        previous = self._previous_states.get(person_id, PersonZoneState.OUTSIDE)

        if (
            previous != PersonZoneState.CRITICAL
            and current_state == PersonZoneState.CRITICAL
        ):
            self._status_banner.publish(
                "CRITICAL: Restricted Area Breach",
                StatusBanner.PRIORITY_CRITICAL,
            )
            self._event_logger.log_event(
                SafetyEvent(
                    timestamp_utc=_utc_now_iso(),
                    event_type=EventType.RESTRICTED_ENTRY,
                    person_id=person_id,
                    zone_name="RESTRICTED ZONE",
                    zone_severity=ZoneSeverity.CRITICAL,
                    confidence=confidence,
                    centroid_x=centroid.x,
                    centroid_y=centroid.y,
                )
            )
            logger.critical("Person %s crossed RED line into RESTRICTED zone.", person_id)

        elif (
            previous == PersonZoneState.CRITICAL
            and current_state != PersonZoneState.CRITICAL
        ):
            self._event_logger.log_event(
                SafetyEvent(
                    timestamp_utc=_utc_now_iso(),
                    event_type=EventType.RESTRICTED_EXIT,
                    person_id=person_id,
                    zone_name="RESTRICTED ZONE",
                    zone_severity=ZoneSeverity.CRITICAL,
                    confidence=confidence,
                    centroid_x=centroid.x,
                    centroid_y=centroid.y,
                )
            )
            logger.info("Person %s exited RESTRICTED ZONE.", person_id)

        self._previous_states[person_id] = current_state

    def prune_stale_ids(self, active_ids: set[int]) -> None:
        stale = set(self._previous_states) - active_ids
        for person_id in stale:
            self._previous_states.pop(person_id, None)

    def reset(self) -> None:
        self._previous_states.clear()


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------


class FrameRenderer:
    """Renders perspective floor zones, detections, and dashboard overlays."""

    def __init__(self, zone_manager: FloorZoneManager) -> None:
        self._zone_manager = zone_manager

    def render(self, frame: np.ndarray, snapshot: MonitoringSnapshot) -> np.ndarray:
        canvas = frame.copy()
        self._draw_perspective_floor_zones(canvas)
        self._draw_detections(canvas, snapshot.detections)
        self._draw_dashboard(canvas, snapshot)
        return canvas

    def _draw_perspective_floor_zones(self, frame: np.ndarray) -> None:
        for polygon, label, color, alpha in self._zone_manager.zone_polygons():
            self._draw_floor_band(frame, polygon, color, alpha, label)

        cv2.polylines(
            frame,
            [self._zone_manager.floor_quad],
            isClosed=True,
            color=(180, 180, 180),
            thickness=2,
        )

        for segment, label, color in self._zone_manager.depth_boundary_segments():
            pt1 = tuple(segment[0].astype(int))
            pt2 = tuple(segment[1].astype(int))
            cv2.line(frame, pt1, pt2, color, 4)
            mid_x = (pt1[0] + pt2[0]) // 2
            mid_y = (pt1[1] + pt2[1]) // 2
            self._draw_tag(frame, label, (mid_x - 40, mid_y - 12), color)

        green_segment = self._zone_manager.near_boundary_segment()
        pt1 = tuple(green_segment[0].astype(int))
        pt2 = tuple(green_segment[1].astype(int))
        cv2.line(frame, pt1, pt2, (0, 255, 0), 3)
        mid_x = (pt1[0] + pt2[0]) // 2
        mid_y = (pt1[1] + pt2[1]) // 2
        self._draw_tag(frame, "GREEN LINE (near)", (mid_x - 55, mid_y + 8), (0, 255, 0))

    @staticmethod
    def _draw_floor_band(
        frame: np.ndarray,
        polygon: np.ndarray,
        color: tuple[int, int, int],
        alpha: float,
        label: str,
    ) -> None:
        overlay = frame.copy()
        cv2.fillPoly(overlay, [polygon], color)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        center = polygon.mean(axis=0).astype(int)
        FrameRenderer._draw_tag(
            frame,
            label,
            (int(center[0]) - 60, int(center[1])),
            color,
        )

    @staticmethod
    def _draw_tag(
        frame: np.ndarray,
        text: str,
        origin: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.55
        thickness = 2
        x, y = origin
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        cv2.rectangle(frame, (x - 4, y - th - 6), (x + tw + 4, y + 4), (15, 15, 15), -1)
        cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

    @staticmethod
    def _draw_detections(frame: np.ndarray, detections: list[DetectionResult]) -> None:
        dashboard_clearance = 165
        sorted_detections = sorted(detections, key=lambda item: item.bbox[0])

        for index, det in enumerate(sorted_detections):
            x1, y1, x2, y2 = det.bbox
            color = _zone_color(det.zone_state)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, det.centroid.as_tuple(), 5, color, -1)

            label = (
                f"ID:{det.tracker_id} {det.confidence:.2f} "
                f"{det.zone_state.value}"
            )
            label_y = y1 - 10 - (index * 22)
            if label_y < dashboard_clearance:
                label_y = y2 + 22 + (index * 22)

            cv2.putText(
                frame,
                label,
                (x1, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )

    def _draw_dashboard(self, frame: np.ndarray, snapshot: MonitoringSnapshot) -> None:
        h, w = frame.shape[:2]
        panel_h = 150
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, panel_h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        lines = [
            f"Total Persons: {snapshot.total_persons}",
            (
                f"Outside: {snapshot.outside_count} | Safe: {snapshot.safe_count} "
                f"| Warning: {snapshot.warning_count} | Restricted: {snapshot.restricted_count}"
            ),
            f"System Status: {snapshot.system_status.value}",
        ]
        if snapshot.display_fps:
            lines.append(f"FPS: {snapshot.fps:.1f}")

        for idx, line in enumerate(lines):
            cv2.putText(
                frame,
                line,
                (15, 28 + idx * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (240, 240, 240),
                2,
                cv2.LINE_AA,
            )

        if snapshot.status_message:
            status_color = _system_status_color(snapshot.system_status)
            cv2.rectangle(frame, (0, h - 55), (w, h), (20, 20, 20), -1)
            cv2.putText(
                frame,
                snapshot.status_message,
                (15, h - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                status_color,
                2,
                cv2.LINE_AA,
            )


# ---------------------------------------------------------------------------
# Video recording
# ---------------------------------------------------------------------------


class VideoRecorder:
    """Writes annotated frames to a VLC-compatible video file with alert audio."""

    _CODEC_CANDIDATES: Final[list[tuple[str, str]]] = [
        ("avc1", ".mp4"),  # H.264 MP4 — best VLC compatibility when finalized
        ("MJPG", ".avi"),  # Motion JPEG AVI — universal fallback
        ("XVID", ".avi"),  # MPEG-4 ASP AVI — secondary fallback
        ("mp4v", ".mp4"),  # Legacy MPEG-4 MP4
    ]

    def __init__(
        self,
        output_path: Path,
        frame_size: tuple[int, int],
        fps: float,
        audio_track: Optional[SessionAudioTrack] = None,
    ) -> None:
        self._output_path = output_path
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer: Optional[cv2.VideoWriter] = None
        self._released = False
        self._frame_count = 0
        self._fps = fps if fps > 0 else 30.0
        self._audio_track = audio_track
        even_size = _even_dimensions(frame_size)
        if even_size != frame_size:
            logger.warning(
                "Adjusted frame size from %s to %s for codec compatibility.",
                frame_size,
                even_size,
            )

        self._writer, self._output_path, codec = self._open_writer(
            output_path,
            even_size,
            self._fps,
        )
        logger.info(
            "Recording output video to %s (codec=%s, fps=%.2f, size=%s, audio=%s)",
            self._output_path,
            codec,
            self._fps,
            even_size,
            "enabled" if self._audio_track is not None else "disabled",
        )
        atexit.register(self.release)

    @classmethod
    def _open_writer(
        cls,
        output_path: Path,
        frame_size: tuple[int, int],
        fps: float,
    ) -> tuple[cv2.VideoWriter, Path, str]:
        """Try codecs in priority order until one opens successfully."""
        stem = output_path.with_suffix("")
        errors: list[str] = []

        for fourcc_str, extension in cls._CODEC_CANDIDATES:
            candidate_path = stem.with_suffix(extension)
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(
                str(candidate_path),
                fourcc,
                fps,
                frame_size,
            )
            if writer.isOpened():
                return writer, candidate_path, fourcc_str

            writer.release()
            errors.append(f"{fourcc_str}{extension}")

        raise RuntimeError(
            "Unable to open video writer. Tried: "
            + ", ".join(errors)
        )

    @property
    def output_path(self) -> Path:
        return self._output_path

    def write(self, frame: np.ndarray) -> None:
        if self._released or self._writer is None:
            return
        self._writer.write(frame)
        self._frame_count += 1

    def release(self) -> None:
        """Finalize the video file so players like VLC can read it."""
        if self._released:
            return
        self._released = True

        if self._writer is not None and self._writer.isOpened():
            self._writer.release()
        self._writer = None

        if (
            self._audio_track is not None
            and self._frame_count > 0
            and self._output_path.exists()
        ):
            self._attach_alert_audio()

        if self._output_path.exists() and self._output_path.stat().st_size > 0:
            logger.info(
                "Output video saved: %s (%d frames, %.1f MB)",
                self._output_path,
                self._frame_count,
                self._output_path.stat().st_size / (1024 * 1024),
            )
        else:
            logger.warning("Output video file is empty or missing: %s", self._output_path)

    def _attach_alert_audio(self) -> None:
        """Synthesize alert audio and mux it into the recorded video."""
        assert self._audio_track is not None
        self._audio_track.finalize(self._frame_count)
        wav_path = self._output_path.with_suffix(".wav")
        audio_pcm = self._audio_track.synthesize(self._frame_count)
        wavfile.write(str(wav_path), SessionAudioTrack.SAMPLE_RATE, audio_pcm)

        ffmpeg_path = _resolve_ffmpeg_executable()
        if ffmpeg_path is None:
            logger.warning(
                "ffmpeg not found. Alert audio saved separately: %s",
                wav_path,
            )
            return

        original_path = self._output_path
        muxed_path = original_path.with_name(f"{original_path.stem}_mux{original_path.suffix}")
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(original_path),
            "-i",
            str(wav_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(muxed_path),
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.error(
                    "ffmpeg audio mux failed: %s",
                    result.stderr.strip() or result.stdout.strip(),
                )
                muxed_path.unlink(missing_ok=True)
                return

            original_path.unlink(missing_ok=True)
            muxed_path.replace(original_path)
            self._output_path = original_path
            wav_path.unlink(missing_ok=True)
            logger.info("Alert audio muxed into output video: %s", self._output_path)
        except OSError:
            logger.exception("Failed to mux alert audio into video.")
            muxed_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Monitoring orchestration
# ---------------------------------------------------------------------------


class SafetyMonitoringApplication:
    """Main application orchestrating detection, tracking, zones, and alerts."""

    WINDOW_NAME: Final[str] = "Construction Site Safety Monitor"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._video_source = VideoSourceManager(config.camera_source)
        self._detector = YOLOPersonDetector(
            config.model_path,
            config.confidence_threshold,
            config.device,
        )
        self._tracker = PersonTracker()
        self._zone_manager = FloorZoneManager(
            config.floor_far_left,
            config.floor_far_right,
            config.floor_near_right,
            config.floor_near_left,
            config.auto_detect_floor,
        )
        self._event_logger = EventLogger(config.resolve_event_log_path())
        self._status_banner = StatusBanner()
        self._alert_manager = AlertManager()
        self._audio_track: Optional[SessionAudioTrack] = None
        self._safe_monitor = SafeZoneMonitor(
            self._event_logger,
            self._status_banner,
            config.warning_cooldown_seconds,
        )
        self._warning_monitor = WarningZoneMonitor(
            self._alert_manager,
            self._event_logger,
            self._status_banner,
            config.warning_cooldown_seconds,
        )
        self._restricted_monitor = RestrictedZoneMonitor(
            self._alert_manager,
            self._event_logger,
            self._status_banner,
        )
        self._renderer = FrameRenderer(self._zone_manager)
        self._recorder: Optional[VideoRecorder] = None
        self._paused = False
        self._frame_index = 0
        self._last_detections: list[DetectionResult] = []
        self._shutdown_complete = False
        self._abort_batch = False
        self._register_signal_handlers()

    def run_all(self, sources: list[str | int]) -> None:
        """Process multiple video sources sequentially."""
        total = len(sources)
        for index, source in enumerate(sources, start=1):
            if self._abort_batch:
                break
            label = source if isinstance(source, str) else f"camera_{source}"
            if isinstance(source, str) and Path(source).exists():
                label = Path(source).stem
            logger.info("Processing input %d/%d: %s", index, total, label)
            self._config.source_label = _sanitize_source_label(str(label))
            self._config.camera_source = source
            self._video_source = VideoSourceManager(source)
            self._shutdown_complete = False
            try:
                self.run()
            finally:
                self._shutdown_complete = False

    def _reset_line_zones(self) -> None:
        self._zone_manager = FloorZoneManager(
            self._config.floor_far_left,
            self._config.floor_far_right,
            self._config.floor_near_right,
            self._config.floor_near_left,
            self._config.auto_detect_floor,
        )
        self._zone_manager.reset()
        self._renderer = FrameRenderer(self._zone_manager)

    def _reset_session_state(self) -> None:
        self._tracker = PersonTracker()
        self._status_banner.reset()
        self._safe_monitor.reset()
        self._warning_monitor.reset()
        self._restricted_monitor.reset()
        self._paused = False
        self._frame_index = 0
        self._last_detections = []
        self._audio_track = None
        self._recorder = None

    def _register_signal_handlers(self) -> None:
        """Ensure video finalization on Ctrl+C and process termination."""
        def _handle_signal(signum: int, _frame: object) -> None:
            logger.info("Signal %s received. Shutting down safely.", signum)
            self._shutdown()
            raise SystemExit(0)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handle_signal)
            except (ValueError, OSError):
                pass

    def run(self) -> None:
        """Execute the main monitoring loop for the current source."""
        try:
            self._reset_session_state()
            self._reset_line_zones()
            self._video_source.open()
            success, bootstrap_frame = self._video_source.read()
            if not success or bootstrap_frame is None:
                raise RuntimeError("Unable to read first frame from video source.")

            frame_height, frame_width = bootstrap_frame.shape[:2]
            self._zone_manager.initialize_for_frame(
                frame_width,
                frame_height,
                bootstrap_frame,
            )

            if self._config.output_video_enabled:
                stream_fps = self._video_source.get_fps()
                self._audio_track = SessionAudioTrack(stream_fps)
                self._alert_manager.attach_audio_track(self._audio_track)
                output_path = self._config.resolve_output_video_path()
                self._recorder = VideoRecorder(
                    output_path,
                    (frame_width, frame_height),
                    stream_fps,
                    audio_track=self._audio_track,
                )

            logger.info(
                "Monitoring started (%s). Controls: Q=Quit, P=Pause, R=Resume",
                self._config.source_label,
            )
            self._main_loop(bootstrap_frame=bootstrap_frame)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
            self._abort_batch = True
        except Exception:
            logger.exception("Unhandled application error.")
            raise
        finally:
            self._shutdown_session()

    def _main_loop(self, bootstrap_frame: Optional[np.ndarray] = None) -> None:
        fps_tracker = _FPSTracker()
        pending_frame = bootstrap_frame
        while True:
            if not self._paused:
                if pending_frame is not None:
                    frame = pending_frame
                    pending_frame = None
                else:
                    success, frame = self._video_source.read()
                    if not success or frame is None:
                        logger.info("End of stream or read failure.")
                        break

                self._frame_index += 1
                if self._frame_index % self._config.frame_skip == 0:
                    self._last_detections = self._process_frame(frame)

                snapshot = self._build_snapshot(self._last_detections, fps_tracker.tick())
                annotated = self._renderer.render(frame, snapshot)

                if self._recorder is not None:
                    self._recorder.write(annotated)
                    if self._audio_track is not None:
                        self._audio_track.advance_frame()

                cv2.imshow(self.WINDOW_NAME, annotated)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                logger.info("Quit requested.")
                self._abort_batch = True
                break
            if key in (ord("p"), ord("P")):
                self._paused = True
                logger.info("Paused.")
            if key in (ord("r"), ord("R")):
                self._paused = False
                logger.info("Resumed.")
            if self._window_closed():
                logger.info("Display window closed. Finalizing recording.")
                break

    def _process_frame(self, frame: np.ndarray) -> list[DetectionResult]:
        detections = self._detector.detect(frame)
        tracked = self._tracker.update(detections)

        results: list[DetectionResult] = []
        active_ids: set[int] = set()

        if tracked.tracker_id is None:
            self._warning_monitor.prune_stale_ids(active_ids)
            self._restricted_monitor.prune_stale_ids(active_ids)
            self._alert_manager.update_critical_alarm(0)
            return results

        for idx in range(len(tracked)):
            tracker_id = tracked.tracker_id[idx]
            if tracker_id is None:
                continue

            person_id = int(tracker_id)
            active_ids.add(person_id)

            bbox_arr = tracked.xyxy[idx]
            bbox = tuple(int(v) for v in bbox_arr)
            confidence = float(tracked.confidence[idx]) if tracked.confidence is not None else 0.0
            floor_point = self._tracker.compute_foot_point(bbox)  # type: ignore[arg-type]
            zone_state = self._zone_manager.classify_point(floor_point)

            self._restricted_monitor.evaluate(person_id, zone_state, confidence, floor_point)
            self._warning_monitor.evaluate(person_id, zone_state, confidence, floor_point)
            self._safe_monitor.evaluate(person_id, zone_state, confidence, floor_point)

            results.append(
                DetectionResult(
                    tracker_id=person_id,
                    confidence=confidence,
                    bbox=bbox,  # type: ignore[arg-type]
                    centroid=floor_point,
                    zone_state=zone_state,
                )
            )

        restricted_count = sum(
            1 for det in results if det.zone_state == PersonZoneState.CRITICAL
        )
        self._alert_manager.update_critical_alarm(restricted_count)
        self._safe_monitor.prune_stale_ids(active_ids)
        self._warning_monitor.prune_stale_ids(active_ids)
        self._restricted_monitor.prune_stale_ids(active_ids)
        return results

    def _build_snapshot(
        self,
        detections: list[DetectionResult],
        fps: float,
    ) -> MonitoringSnapshot:
        outside_count = sum(
            1 for d in detections if d.zone_state == PersonZoneState.OUTSIDE
        )
        safe_count = sum(1 for d in detections if d.zone_state == PersonZoneState.SAFE)
        warning_count = sum(
            1 for d in detections if d.zone_state == PersonZoneState.WARNING
        )
        restricted_count = sum(
            1 for d in detections if d.zone_state == PersonZoneState.CRITICAL
        )

        banner_message = self._status_banner.read()
        if restricted_count > 0:
            system_status = SystemStatus.CRITICAL
            status_message = banner_message or "CRITICAL: Restricted Area Breach"
        elif warning_count > 0:
            system_status = SystemStatus.WARNING
            status_message = banner_message or "WARNING: Do Not Enter Restricted Zone"
        elif safe_count > 0:
            system_status = SystemStatus.SAFE
            status_message = banner_message or "SAFE: Monitored Area"
        elif outside_count > 0:
            system_status = SystemStatus.SAFE
            status_message = banner_message
        else:
            system_status = SystemStatus.SAFE
            status_message = banner_message

        return MonitoringSnapshot(
            detections=detections,
            total_persons=len(detections),
            outside_count=outside_count,
            safe_count=safe_count,
            warning_count=warning_count,
            restricted_count=restricted_count,
            system_status=system_status,
            fps=fps,
            status_message=status_message,
            display_fps=self._config.display_fps,
        )

    def _window_closed(self) -> bool:
        """Detect when the user closes the OpenCV window with the X button."""
        try:
            return cv2.getWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1
        except cv2.error:
            return True

    def _shutdown_session(self) -> None:
        if self._shutdown_complete:
            return
        self._shutdown_complete = True

        self._alert_manager.shutdown()
        if self._recorder is not None:
            self._recorder.release()
            self._recorder = None
        if self._video_source.is_opened:
            self._video_source.release()
        cv2.destroyAllWindows()
        logger.info("Session shutdown complete for source: %s", self._config.source_label)

    def _shutdown(self) -> None:
        """Full application shutdown (alias for session shutdown)."""
        self._shutdown_session()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _even_dimensions(size: tuple[int, int]) -> tuple[int, int]:
    """H.264 encoders require even width and height."""
    width, height = size
    return width - (width % 2), height - (height % 2)


def _resolve_ffmpeg_executable() -> Optional[str]:
    """Locate ffmpeg from PATH or the bundled imageio-ffmpeg package."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return bundled
    except ImportError:
        pass
    return None


def _zone_color(state: PersonZoneState) -> tuple[int, int, int]:
    mapping = {
        PersonZoneState.OUTSIDE: (200, 200, 200),
        PersonZoneState.SAFE: (0, 200, 0),
        PersonZoneState.WARNING: (0, 220, 255),
        PersonZoneState.CRITICAL: (0, 0, 255),
    }
    return mapping[state]


def _system_status_color(status: SystemStatus) -> tuple[int, int, int]:
    mapping = {
        SystemStatus.SAFE: (0, 220, 0),
        SystemStatus.WARNING: (0, 220, 255),
        SystemStatus.CRITICAL: (0, 0, 255),
    }
    return mapping[status]


class _FPSTracker:
    """Simple rolling FPS calculator."""

    def __init__(self, window_size: int = 30) -> None:
        self._timestamps: list[float] = []
        self._window_size = window_size

    def tick(self) -> float:
        now = time.perf_counter()
        self._timestamps.append(now)
        if len(self._timestamps) > self._window_size:
            self._timestamps.pop(0)
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed


def _sanitize_source_label(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label)
    return cleaned.strip("_") or "source"


def discover_input_videos(directory: Path) -> list[Path]:
    """Return sorted video files from an input directory."""
    if not directory.exists():
        logger.warning("Input directory does not exist: %s", directory)
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Construction Site Safety Anomaly Detection – "
            "Multi-Level Restricted Area Monitoring POC"
        )
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Single video file path (default: process all videos in input_videos/)",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Process all videos in this folder (default: input_videos)",
    )
    parser.add_argument(
        "--webcam",
        action="store_true",
        help="Use webcam (index 0) instead of uploaded input videos",
    )
    parser.add_argument(
        "--no-auto-floor",
        action="store_true",
        help="Disable automatic floor detection; use default perspective quad",
    )
    parser.add_argument(
        "--model",
        default=MODEL_PATH,
        help="YOLOv8 model weights path (default: yolov8n.pt)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=CONFIDENCE_THRESHOLD,
        help="Detection confidence threshold (default: 0.45)",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=FRAME_SKIP,
        help="Process every Nth frame (default: 1)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Inference device: cpu, cuda, cuda:0, etc. (default: cpu)",
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="Disable annotated output video recording",
    )
    parser.add_argument(
        "--no-display-fps",
        action="store_true",
        help="Hide FPS counter on overlay",
    )
    return parser


def parse_camera_source(source: str) -> str | int:
    if source.isdigit():
        return int(source)
    return source


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    configure_logging()

    config = AppConfig(
        model_path=args.model,
        confidence_threshold=args.conf,
        frame_skip=max(1, args.frame_skip),
        display_fps=not args.no_display_fps,
        output_video_enabled=not args.no_video and OUTPUT_VIDEO_ENABLED,
        device=args.device,
        auto_detect_floor=not args.no_auto_floor,
    )

    app = SafetyMonitoringApplication(config)

    if args.webcam:
        config.camera_source = 0
        config.source_label = "webcam"
        logger.info("Starting with webcam input (--webcam)")
        app.run()
        return 0

    input_dir = Path(args.input_dir or INPUT_VIDEO_DIRECTORY)
    if args.source is not None:
        source_path = Path(args.source)
        if source_path.is_file():
            config.camera_source = str(source_path)
            config.source_label = _sanitize_source_label(source_path.stem)
            logger.info("Processing single video: %s", source_path)
            app.run()
            return 0
        config.camera_source = parse_camera_source(args.source)
        config.source_label = _sanitize_source_label(str(args.source))
        logger.info("Starting with source=%s", config.camera_source)
        app.run()
        return 0

    videos = discover_input_videos(input_dir)
    if not videos:
        logger.error(
            "No videos found in %s. Upload .mp4 files to input_videos/ "
            "or use --source path\\to\\video.mp4 or --webcam for live camera.",
            input_dir,
        )
        return 1

    logger.info(
        "Processing %d video(s) from %s (input videos only, not webcam).",
        len(videos),
        input_dir,
    )
    app.run_all([str(path) for path in videos])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
