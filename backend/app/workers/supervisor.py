"""Process supervisor that spawns/terminates one worker per active camera."""

from __future__ import annotations

import multiprocessing as mp
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import ConflictError, WorkerError
from app.workers.camera_worker import run_camera_worker
from app.workers.messages import DetectionMessage, WorkerConfig
from app.workers.registry import CameraWorkerRegistry, WorkerHandle

logger = get_logger(__name__)

_JOIN_TIMEOUT_SECONDS = 5.0


class WorkerSupervisor:
    """Owns the IPC queue and the lifecycle of every camera worker process."""

    def __init__(self) -> None:
        settings = get_settings()
        # ``spawn`` behaves identically on Windows and Linux and avoids
        # fork-related issues with the async event loop / CV libraries.
        self._ctx: mp.context.SpawnContext = mp.get_context("spawn")
        self._queue: mp.Queue[DetectionMessage] = self._ctx.Queue(maxsize=1000)
        self._registry = CameraWorkerRegistry()
        self._max_active = settings.max_active_cameras

    @property
    def event_queue(self) -> mp.Queue[DetectionMessage]:
        return self._queue

    def is_running(self, camera_id: str) -> bool:
        return self._registry.is_running(camera_id)

    def active_ids(self) -> list[str]:
        self._registry.prune_dead()
        return self._registry.active_ids()

    def activate(self, config: WorkerConfig) -> None:
        """Spawn a worker process for ``config.camera_id``."""

        self._registry.prune_dead()
        if self._registry.is_running(config.camera_id):
            raise ConflictError(f"Camera {config.camera_id} is already active")
        if len(self._registry.active_ids()) >= self._max_active:
            raise ConflictError(f"Maximum of {self._max_active} active cameras reached")

        stop_event = self._ctx.Event()
        process = self._ctx.Process(
            target=run_camera_worker,
            args=(config, self._queue, stop_event),
            name=f"camera-worker-{config.camera_id}",
            daemon=True,
        )
        try:
            process.start()
        except Exception as exc:
            logger.exception("Failed to start worker for %s", config.camera_id)
            raise WorkerError(f"Failed to start camera worker: {exc}") from exc

        self._registry.add(
            WorkerHandle(
                camera_id=config.camera_id,
                process=process,
                stop_event=stop_event,
                config=config,
            )
        )
        logger.info("Activated camera worker %s (pid=%s)", config.camera_id, process.pid)

    def deactivate(self, camera_id: str) -> bool:
        """Gracefully stop the worker for ``camera_id``. Returns True if stopped."""

        handle = self._registry.remove(camera_id)
        if handle is None:
            return False
        handle.stop_event.set()
        handle.process.join(timeout=_JOIN_TIMEOUT_SECONDS)
        if handle.process.is_alive():
            logger.warning("Worker %s did not exit gracefully; terminating", camera_id)
            handle.process.terminate()
            handle.process.join(timeout=_JOIN_TIMEOUT_SECONDS)
        logger.info("Deactivated camera worker %s", camera_id)
        return True

    def shutdown(self) -> None:
        """Stop every worker (called on application shutdown)."""

        for handle in self._registry.all_handles():
            self.deactivate(handle.camera_id)


@lru_cache
def get_supervisor() -> WorkerSupervisor:
    """Return the process-wide supervisor singleton."""

    return WorkerSupervisor()
