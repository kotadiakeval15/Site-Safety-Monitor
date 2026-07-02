"""Real-time alert WebSocket controller."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.realtime.websocket_manager import alert_ws_manager

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)


@router.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Stream real-time alerts to authenticated clients."""

    if not token:
        await websocket.close(code=4401)
        return
    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=4401)
        return

    await alert_ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection open; ignore any client messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await alert_ws_manager.disconnect(websocket)
    except Exception:
        await alert_ws_manager.disconnect(websocket)
