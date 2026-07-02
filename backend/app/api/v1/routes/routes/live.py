"""Live annotated-frame streaming controller.

Worker processes publish the latest annotated JPEG to
``{live_frames_dir}/{camera_id}.jpg``. These endpoints serve that file as a
single snapshot or as an MJPEG stream. Because ``<img>`` tags cannot send
Authorization headers, a ``?token=`` query parameter is also accepted.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.exceptions.base import NotFoundError, UnauthorizedError

router = APIRouter(prefix="/live", tags=["live"])
_bearer = HTTPBearer(auto_error=False)


async def authorize_stream(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = Query(default=None),
) -> UUID:
    """Authenticate via Bearer header or ``?token=`` query parameter."""

    raw = credentials.credentials if credentials else token
    if not raw:
        raise UnauthorizedError("Missing authentication token")
    try:
        payload = decode_access_token(raw)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc
    return UUID(payload["sub"])


def _frame_path(camera_id: UUID) -> Path:
    settings = get_settings()
    return Path(settings.live_frames_dir) / f"{camera_id}.jpg"


@router.get("/{camera_id}.jpg")
async def live_frame(camera_id: UUID, _user: UUID = Depends(authorize_stream)) -> Response:
    """Return the latest annotated frame as a single JPEG."""

    path = _frame_path(camera_id)
    if not path.exists():
        raise NotFoundError("No live frame available for this camera")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.get("/{camera_id}/mjpeg")
async def live_mjpeg(camera_id: UUID, _user: UUID = Depends(authorize_stream)) -> StreamingResponse:
    """Stream annotated frames as multipart MJPEG."""

    path = _frame_path(camera_id)

    async def _generate():
        boundary = b"--frame"
        while True:
            if path.exists():
                data = path.read_bytes()
                yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        _generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
