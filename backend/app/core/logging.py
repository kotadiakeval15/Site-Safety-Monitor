"""Structured JSON logging with hourly file rotation.

A new log file is created every hour. The active file is ``backend.log`` and,
on rotation, it is renamed using the pattern ``dd-mm-yyyy_hh-mm-ss.log``.

The requested format uses ``:`` separators (``dd:mm:yyyy_hh:mm:ss.log``) but the
colon is an illegal filename character on Windows/NTFS, so we substitute ``-``
while preserving the exact field order and layout.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.request_context import get_request_id

# Suffix appended by TimedRotatingFileHandler; matches ``dd-mm-yyyy_hh-mm-ss``.
_ROTATED_SUFFIX = "%d-%m-%Y_%H-%M-%S"
_ROTATED_RE = re.compile(r"^\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2}$")


class JSONFormatter(logging.Formatter):
    """Render each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            payload["data"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class HourlyRotatingHandler(logging.handlers.TimedRotatingFileHandler):
    """Timed handler that names rotated files ``dd-mm-yyyy_hh-mm-ss.log``."""

    def __init__(self, log_dir: Path, backup_count: int = 168) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(
            filename=str(log_dir / "backend.log"),
            when="H",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
            utc=False,
        )
        self._log_dir = log_dir
        self.suffix = _ROTATED_SUFFIX
        self.extMatch = re.compile(r"^\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2}(\.\w+)?$")

    def namer(self, default_name: str) -> str:  # type: ignore[override]
        """Produce ``<log_dir>/dd-mm-yyyy_hh-mm-ss.log`` for a rotated file."""

        base = os.path.basename(default_name)
        # default_name looks like "backend.log.05-01-2026_14-00-00"
        parts = base.split(".log.")
        stamp = parts[-1] if len(parts) > 1 else base
        return str(self._log_dir / f"{stamp}.log")


def setup_logging() -> None:
    """Configure root logging with hourly rotation + console output."""

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = HourlyRotatingHandler(Path(settings.logs_dir))
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(JSONFormatter())
    root.addHandler(console)

    # Quiet noisy third-party loggers.
    for noisy in ("uvicorn.access", "watchfiles.main"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""

    return logging.getLogger(name)


def log_extra(logger: logging.Logger, level: int, message: str, **extra: Any) -> None:
    """Emit a log line carrying structured ``extra`` fields."""

    record = logger.makeRecord(logger.name, level, "", 0, message, (), None)
    record.extra_data = extra
    logger.handle(record)
