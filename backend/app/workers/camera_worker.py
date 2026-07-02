"""Child-process entrypoint that runs the AI pipeline for one camera.

Executed in a dedicated OS process (spawned by :class:`WorkerSupervisor`). Heavy
imports (OpenCV, the ``ai_repo`` pipeline) happen lazily inside :func:`run_camera_worker`
so the parent API process never needs the CV stack loaded.
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import tempfile
import time
from multiprocessing.synchronize import Event as EventType
from queue import Full
from typing import TYPE_CHECKING

from app.workers.messages import DetectionMessage, WorkerConfig

if TYPE_CHECKING:  # pragma: no cover
    from multiprocessing import Queue

logger = logging.getLogger("camera_worker")

# Matches frontend red buzzer auto-stop (10–15 s window).
RED_BUZZ_SECONDS = 12.0
# Helmet violation alerts only — independent of zone/line cooldowns.
HELMET_ALERT_COOLDOWN_SECONDS = 600.0


def _write_live_frame(directory: str, camera_id: str, jpeg_bytes: bytes) -> None:
    """Atomically publish the latest annotated frame for the live view."""

    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, f"{camera_id}.jpg")
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(jpeg_bytes)
        os.replace(tmp_path, target)
    except OSError:
        logger.exception("Failed to publish live frame for %s", camera_id)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _parse_source(stream_url: str) -> str | int:
    return int(stream_url) if stream_url.isdigit() else stream_url


def run_camera_worker(
    config: WorkerConfig,
    event_queue: Queue[DetectionMessage],
    stop_event: EventType,
) -> None:
    """Run the detection loop until ``stop_event`` is set."""

    logging.basicConfig(level=logging.INFO)
    try:
        import cv2
        from ai_repo.pipelines import SafetyPipeline
        from ai_repo.tracking import CooldownTracker
        from ai_repo.zones import LineConfig
    except Exception:
        logger.exception("Camera worker %s could not import AI stack", config.camera_id)
        return

    line_config = LineConfig.from_items(config.line_items())

    try:
        pipeline = SafetyPipeline(
            person_model_path=config.yolo_model_path,
            helmet_model_path=config.helmet_model_path,
            confidence=config.confidence,
            device=config.device,
        )
    except Exception:
        logger.exception("Camera worker %s failed to load models", config.camera_id)
        return

    cooldown = CooldownTracker(config.cooldown_seconds)
    red_cooldown = CooldownTracker(config.cooldown_seconds + RED_BUZZ_SECONDS)
    helmet_cooldown = CooldownTracker(HELMET_ALERT_COOLDOWN_SECONDS)
    source = _parse_source(config.stream_url)
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        logger.error(
            "Camera worker %s could not open source %s", config.camera_id, config.stream_url
        )
        return

    logger.info("Camera worker %s started for %s", config.camera_id, config.stream_url)
    window_name = f"Detection - Camera {config.camera_id}"
    window_ready = _init_window(cv2, config.show_window, window_name)
    frame_index = 0
    read_failures = 0
    max_read_failures = 30
    worker_zones: dict[int, str] = {}
    try:
        while not stop_event.is_set():
            ok, frame = capture.read()
            if not ok or frame is None:
                read_failures += 1
                if isinstance(source, str):
                    if read_failures >= max_read_failures:
                        logger.error(
                            "Camera worker %s cannot decode %s after %s attempts. "
                            "Re-upload the video (AV1/WhatsApp clips are converted on upload).",
                            config.camera_id,
                            config.stream_url,
                            read_failures,
                        )
                        break
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.02)
                    continue
                time.sleep(0.05)
                continue

            read_failures = 0
            frame_index += 1
            frame_skip = (
                1 if config.detection_mode == "helmet" else config.frame_skip
            )
            if frame_skip > 1 and frame_index % frame_skip != 0:
                continue

            try:
                detections, annotated = pipeline.process_frame(
                    frame, config.camera_id, line_config, config.detection_mode
                )
            except Exception:
                logger.exception("Frame processing error for %s", config.camera_id)
                continue

            ok_enc, buffer = cv2.imencode(".jpg", annotated)
            annotated_b64: str | None = None
            if ok_enc:
                jpeg = buffer.tobytes()
                _write_live_frame(config.live_frames_dir, config.camera_id, jpeg)
                annotated_b64 = base64.b64encode(jpeg).decode("ascii")

            if window_ready:
                try:
                    cv2.imshow(window_name, annotated)
                    cv2.waitKey(1)
                except Exception:
                    window_ready = False

            _emit_events(
                config,
                detections,
                annotated_b64,
                cooldown,
                red_cooldown,
                helmet_cooldown,
                event_queue,
                worker_zones,
            )
            time.sleep(0.005)
    finally:
        capture.release()
        if window_ready:
            with contextlib.suppress(Exception):
                cv2.destroyWindow(window_name)
        logger.info("Camera worker %s stopped", config.camera_id)


def _init_window(cv2_module, show_window: bool, window_name: str) -> bool:
    """Best-effort creation of a preview window; returns False when unavailable."""

    if not show_window:
        return False
    try:
        cv2_module.namedWindow(window_name, cv2_module.WINDOW_NORMAL)
        return True
    except Exception:
        logger.warning("Preview window unavailable (headless environment?)")
        return False


def _emit_events(
    config: WorkerConfig,
    detections: list,
    annotated_b64: str | None,
    cooldown,
    red_cooldown,
    helmet_cooldown,
    event_queue: Queue[DetectionMessage],
    worker_zones: dict[int, str],
) -> None:
    """Translate pipeline detections into throttled IPC messages."""

    severity_by_line = {"green": "level_1", "yellow": "level_2", "red": "danger"}
    active_ids = {int(det["worker_id"]) for det in detections}

    for det in detections:
        worker_id = int(det["worker_id"])
        zone = det.get("zone_color", "safe")
        previous = worker_zones.get(worker_id, "safe")
        worker_zones[worker_id] = zone

        if previous == "red" and zone != "red":
            red_cooldown.reset(worker_id, "red_zone", "occupied")
            _put(
                event_queue,
                DetectionMessage(
                    camera_id=config.camera_id,
                    worker_id=worker_id,
                    violation_type="zone_exit",
                    severity="danger",
                    crossed_line="red",
                    confidence=float(det.get("confidence", 0.0)),
                    message=f"Worker {worker_id} exited RED restricted area",
                ),
            )

        if det.get("helmet_status") == "helmet_violation" and helmet_cooldown.should_fire(
            worker_id, "helmet_violation"
        ):
            _put(
                event_queue,
                DetectionMessage(
                    camera_id=config.camera_id,
                    worker_id=worker_id,
                    violation_type="helmet_violation",
                    severity="danger",
                    confidence=float(det.get("confidence", 0.0)),
                    bbox=list(det.get("bbox", []) or []),
                    foot_x=det.get("foot_x"),
                    foot_y=det.get("foot_y"),
                    screenshot_base64=annotated_b64,
                    message=f"Helmet violation - Worker {worker_id}",
                ),
            )

        if zone == "yellow" and cooldown.should_fire(worker_id, "yellow_zone", "occupied"):
            _put(
                event_queue,
                DetectionMessage(
                    camera_id=config.camera_id,
                    worker_id=worker_id,
                    violation_type="line_crossing",
                    severity=severity_by_line["yellow"],
                    crossed_line="yellow",
                    confidence=float(det.get("confidence", 0.0)),
                    bbox=list(det.get("bbox", []) or []),
                    foot_x=det.get("foot_x"),
                    foot_y=det.get("foot_y"),
                    screenshot_base64=annotated_b64,
                    message=f"Worker {worker_id} entered YELLOW warning zone",
                    zone_id=config.zone_for_line("yellow"),
                ),
            )

        if zone == "red" and red_cooldown.should_fire(worker_id, "red_zone", "occupied"):
            _put(
                event_queue,
                DetectionMessage(
                    camera_id=config.camera_id,
                    worker_id=worker_id,
                    violation_type="line_crossing",
                    severity="danger",
                    crossed_line="red",
                    confidence=float(det.get("confidence", 0.0)),
                    bbox=list(det.get("bbox", []) or []),
                    foot_x=det.get("foot_x"),
                    foot_y=det.get("foot_y"),
                    screenshot_base64=annotated_b64,
                    message=f"Worker {worker_id} entered RED restricted area",
                    zone_id=config.zone_for_line("red"),
                ),
            )

    for stale_id in set(worker_zones) - active_ids:
        previous = worker_zones.pop(stale_id)
        if previous == "red":
            red_cooldown.reset(stale_id, "red_zone", "occupied")
            _put(
                event_queue,
                DetectionMessage(
                    camera_id=config.camera_id,
                    worker_id=stale_id,
                    violation_type="zone_exit",
                    severity="danger",
                    crossed_line="red",
                    message=f"Worker {stale_id} left frame (was in RED area)",
                ),
            )


def _put(event_queue: Queue[DetectionMessage], message: DetectionMessage) -> None:
    try:
        event_queue.put_nowait(message)
    except Full:
        logger.warning("Event queue full; dropping detection for %s", message.camera_id)
