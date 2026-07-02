"""Screenshot / image persistence helpers."""

from __future__ import annotations

import base64
import binascii
import uuid
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


def decode_base64_image(data: str | None) -> bytes | None:
    """Decode a (possibly data-URI prefixed) base64 image string to bytes."""

    if not data:
        return None
    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        return base64.b64decode(data)
    except (binascii.Error, ValueError):
        logger.warning("Failed to decode base64 image payload")
        return None


def save_screenshot(
    directory: str,
    camera_id: str,
    worker_id: int,
    data_b64: str | None,
) -> str | None:
    """Persist a base64 JPEG screenshot and return the relative file path."""

    raw = decode_base64_image(data_b64)
    if raw is None:
        return None
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{camera_id}_{worker_id}_{uuid.uuid4().hex}.jpg"
    path = target_dir / filename
    try:
        path.write_bytes(raw)
    except OSError:
        logger.exception("Failed to write screenshot to %s", path)
        return None
    return str(path)
