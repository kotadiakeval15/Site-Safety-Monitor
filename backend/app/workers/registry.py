"""Registry tracking one live worker process per active camera."""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing.context import SpawnProcess
from multiprocessing.synchronize import Event as EventType

from app.core.logging import get_logger
from app.workers.messages import WorkerConfig

logger = get_logger(__name__)


@dataclass
class WorkerHandle:
    """Handle to a running camera worker process."""

    camera_id: str
    process: SpawnProcess
    stop_event: EventType
    config: WorkerConfig


class CameraWorkerRegistry:
    """Thread-safe-ish in-memory map of ``camera_id -> WorkerHandle``.

    Access is confined to the single asyncio event loop / supervisor, so no
    additional locking is required.
    """

    def __init__(self) -> None:
        self._handles: dict[str, WorkerHandle] = {}

    def add(self, handle: WorkerHandle) -> None:
        self._handles[handle.camera_id] = handle

    def get(self, camera_id: str) -> WorkerHandle | None:
        return self._handles.get(camera_id)

    def remove(self, camera_id: str) -> WorkerHandle | None:
        return self._handles.pop(camera_id, None)

    def is_running(self, camera_id: str) -> bool:
        handle = self._handles.get(camera_id)
        return handle is not None and handle.process.is_alive()

    def active_ids(self) -> list[str]:
        return [cid for cid, h in self._handles.items() if h.process.is_alive()]

    def all_handles(self) -> list[WorkerHandle]:
        return list(self._handles.values())

    def prune_dead(self) -> None:
        """Drop handles whose process has exited on its own."""

        dead = [cid for cid, h in self._handles.items() if not h.process.is_alive()]
        for cid in dead:
            logger.warning("Pruning dead camera worker %s", cid)
            self._handles.pop(cid, None)
