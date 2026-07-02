"""In-process WebSocket connection manager for broadcasting alerts."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class AlertWebSocketManager:
    """Track connected clients and broadcast alert payloads to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket connected (total=%d)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket disconnected (total=%d)", len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send ``payload`` as JSON to every connected client."""

        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_json(payload)
            except Exception:
                dead.append(connection)
        if dead:
            async with self._lock:
                for connection in dead:
                    self._connections.discard(connection)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


alert_ws_manager = AlertWebSocketManager()
