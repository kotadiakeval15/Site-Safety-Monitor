"""Aggregate all v1 routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
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

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(zones.router)
api_router.include_router(cameras.router)
api_router.include_router(detections.router)
api_router.include_router(statistics.router)
api_router.include_router(audit.router)
api_router.include_router(live.router)
api_router.include_router(websocket.router)
