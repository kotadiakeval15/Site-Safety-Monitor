"""Video helpers: normalize uploads to OpenCV-friendly H.264 MP4."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def transcode_to_h264_mp4(source: Path, destination: Path, *, timeout_seconds: int = 600) -> bool:
    """Re-encode *source* to H.264 MP4 suitable for OpenCV ``VideoCapture``.

    WhatsApp and many phone cameras produce AV1/HEVC clips that the slim OpenCV
    build in our container cannot decode. ffmpeg normalizes them to baseline
    H.264 with ``yuv420p`` pixel format.

    Returns ``True`` when *destination* was written successfully.
    """

    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not installed; skipping video transcode for %s", source)
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(destination),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out transcoding %s", source)
        if destination.resolve() != source.resolve():
            destination.unlink(missing_ok=True)
        return False

    if result.returncode != 0:
        logger.warning(
            "ffmpeg failed for %s (exit %s): %s",
            source,
            result.returncode,
            (result.stderr or "")[-500:],
        )
        if destination.resolve() != source.resolve():
            destination.unlink(missing_ok=True)
        return False

    if not destination.is_file() or destination.stat().st_size == 0:
        if destination.resolve() != source.resolve():
            destination.unlink(missing_ok=True)
        return False

    return True


def normalize_uploaded_video(source: Path, camera_id: str, uploads_dir: Path) -> Path:
    """Return the path the camera worker should use after optional transcode.

    Always targets ``{uploads_dir}/{camera_id}.mp4``. When ffmpeg succeeds the
    returned file is H.264. When ffmpeg is unavailable or fails, the original
    upload is kept (same extension) so local tests with tiny fake clips still work.
    """

    target_mp4 = uploads_dir / f"{camera_id}.mp4"
    for existing in uploads_dir.glob(f"{camera_id}*"):
        if existing == source or existing == target_mp4:
            continue
        if existing.name.startswith(f"{camera_id}_upload"):
            existing.unlink(missing_ok=True)
        elif existing.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
            existing.unlink(missing_ok=True)

    if source.resolve() == target_mp4.resolve():
        staging = uploads_dir / f"{camera_id}.transcode.tmp.mp4"
        if transcode_to_h264_mp4(source, staging):
            staging.replace(target_mp4)
            return target_mp4
        return source

    if transcode_to_h264_mp4(source, target_mp4):
        source.unlink(missing_ok=True)
        return target_mp4

    # Fallback: keep the raw upload (tests / already-compatible files).
    if source.suffix.lower() == ".mp4":
        source.replace(target_mp4)
        return target_mp4
    return source
