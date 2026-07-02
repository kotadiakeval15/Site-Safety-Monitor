"""Multiprocessing camera-worker subsystem.

The FastAPI backend activates a camera by spawning one OS process per camera
(true parallelism for CPU-bound CV work). Workers stream detection events back
over a ``multiprocessing.Queue`` which an async drainer persists and broadcasts.
"""

from app.workers.messages import DetectionMessage, WorkerConfig, WorkerLineConfig
from app.workers.supervisor import WorkerSupervisor, get_supervisor

__all__ = [
    "DetectionMessage",
    "WorkerConfig",
    "WorkerLineConfig",
    "WorkerSupervisor",
    "get_supervisor",
]
