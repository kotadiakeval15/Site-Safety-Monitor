"""Async task that drains worker detection events into the database.

Worker processes are CPU-bound and isolated; they push :class:`DetectionMessage`
objects onto a ``multiprocessing.Queue``. This drainer runs in the main event
loop, reads messages via a thread executor (the queue ``get`` is blocking),
persists them through :class:`DetectionService`, and broadcasts alerts over the
WebSocket manager.
"""

from __future__ import annotations

import asyncio
import contextlib
import queue as queue_mod
from typing import TYPE_CHECKING

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.detection_service import DetectionService
from app.workers.messages import DetectionMessage

if TYPE_CHECKING:  # pragma: no cover
    import multiprocessing as mp

logger = get_logger(__name__)

_POLL_TIMEOUT = 0.5


class EventDrainer:
    """Owns the background task consuming the worker event queue."""

    def __init__(self, event_queue: mp.Queue[DetectionMessage]) -> None:
        self._queue = event_queue
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run(), name="event-drainer")
            logger.info("Event drainer started")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("Event drainer stopped")

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                message = await loop.run_in_executor(None, self._blocking_get)
            except asyncio.CancelledError:
                break
            if message is None:
                continue
            try:
                await self._handle(message)
            except Exception:
                logger.exception("Failed to persist detection message")

    def _blocking_get(self) -> DetectionMessage | None:
        try:
            return self._queue.get(timeout=_POLL_TIMEOUT)
        except queue_mod.Empty:
            return None

    async def _handle(self, message: DetectionMessage) -> None:
        if message.violation_type == "zone_exit":
            from app.realtime.websocket_manager import alert_ws_manager

            await alert_ws_manager.broadcast(
                {
                    "type": "zone_exit",
                    "camera_id": message.camera_id,
                    "worker_id": message.worker_id,
                    "crossed_line": message.crossed_line,
                    "message": message.message,
                }
            )
            return

        async with AsyncSessionLocal() as session:
            service = DetectionService(session)
            payload = await service.ingest_worker_event(message)
            await session.commit()
        if payload is not None:
            from app.realtime.websocket_manager import alert_ws_manager

            await alert_ws_manager.broadcast(payload)
