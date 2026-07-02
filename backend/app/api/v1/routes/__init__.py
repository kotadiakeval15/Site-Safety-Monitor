"""API v1 route controllers."""

from app.api.v1.routes.routes import (
    audit,
    auth,
    cameras,
    detections,
    health,
    live,
    statistics,
    websocket,
    zones,
)

__all__ = [
    "audit",
    "auth",
    "cameras",
    "detections",
    "health",
    "live",
    "statistics",
    "websocket",
    "zones",
]
