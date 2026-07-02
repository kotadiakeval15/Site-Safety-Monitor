"""Camera CRUD + activation controller."""

from __future__ import annotations

import mimetypes
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, require_admin, require_viewer
from app.api.v1.routes.routes.live import authorize_stream
from app.core.config import get_settings
from app.exceptions.base import NotFoundError
from app.models.user import User
from app.responses import success_response
from app.schemas.camera import CameraCreate, CameraUpdate
from app.services.camera_service import CameraService
from app.services.zone_service import ZoneService

router = APIRouter(prefix="/cameras", tags=["cameras"])

_RANGE_CHUNK = 64 * 1024


def _serve_file_with_range(path: Path, request: Request, media_type: str) -> Response:
    """Serve a file, honoring a single HTTP ``Range`` header for video seeking."""

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header and range_header.startswith("bytes="):
        start_s, _, end_s = range_header[len("bytes=") :].partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)
        start = min(start, end)
        length = end - start + 1

        def _iter_range() -> Iterator[bytes]:
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(_RANGE_CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return StreamingResponse(
            _iter_range(), status_code=206, media_type=media_type, headers=headers
        )

    def _iter_all() -> Iterator[bytes]:
        with path.open("rb") as handle:
            while chunk := handle.read(_RANGE_CHUNK):
                yield chunk

    headers = {"Accept-Ranges": "bytes", "Content-Length": str(file_size)}
    return StreamingResponse(_iter_all(), media_type=media_type, headers=headers)


@router.get("")
async def list_cameras(session: DbSession, _user: User = Depends(require_viewer)) -> dict:
    cameras = await CameraService(session).list_cameras()
    return success_response([c.model_dump(mode="json") for c in cameras])


@router.get("/{camera_id}")
async def get_camera(
    camera_id: UUID, session: DbSession, _user: User = Depends(require_viewer)
) -> dict:
    camera = await CameraService(session).get_camera(camera_id)
    return success_response(camera.model_dump(mode="json"))


@router.get("/{camera_id}/zones")
async def list_camera_zones(
    camera_id: UUID, session: DbSession, _user: User = Depends(require_viewer)
) -> dict:
    zones = await ZoneService(session).list_for_camera(camera_id)
    return success_response([z.model_dump(mode="json") for z in zones])


@router.post("", status_code=201)
async def create_camera(
    payload: CameraCreate, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    camera = await CameraService(session).create_camera(payload, admin.user_id)
    return success_response(camera.model_dump(mode="json"), message="Camera created")


@router.put("/{camera_id}")
async def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    session: DbSession,
    admin: User = Depends(require_admin),
) -> dict:
    camera = await CameraService(session).update_camera(camera_id, payload, admin.user_id)
    return success_response(camera.model_dump(mode="json"), message="Camera updated")


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: UUID, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    await CameraService(session).delete_camera(camera_id, admin.user_id)
    return success_response(message="Camera deleted")


@router.post("/{camera_id}/video")
async def upload_camera_video(
    camera_id: UUID,
    session: DbSession,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
) -> dict:
    """Upload a recorded video that the AI worker will process for this camera."""

    camera = await CameraService(session).upload_video(camera_id, file, admin.user_id)
    return success_response(camera.model_dump(mode="json"), message="Video uploaded")


@router.get("/{camera_id}/video")
async def stream_camera_video(
    camera_id: UUID,
    request: Request,
    session: DbSession,
    _user: UUID = Depends(authorize_stream),
) -> Response:
    """Stream the uploaded video (range-aware) so the UI can play it back."""

    camera = await CameraService(session).get_camera(camera_id)
    uploads_dir = Path(get_settings().uploads_dir).resolve()
    path = Path(camera.stream_url).resolve() if camera.stream_url else None
    if path is None or uploads_dir not in path.parents or not path.is_file():
        raise NotFoundError("No uploaded video for this camera")
    media_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    return _serve_file_with_range(path, request, media_type)


@router.post("/{camera_id}/activate")
async def activate_camera(
    camera_id: UUID, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    """Activate a camera: spawns its background AI worker process."""

    camera = await CameraService(session).activate_camera(camera_id, admin.user_id)
    return success_response(camera.model_dump(mode="json"), message="Camera activated")


@router.post("/{camera_id}/deactivate")
async def deactivate_camera(
    camera_id: UUID, session: DbSession, admin: User = Depends(require_admin)
) -> dict:
    """Deactivate a camera: gracefully terminates its worker process."""

    camera = await CameraService(session).deactivate_camera(camera_id, admin.user_id)
    return success_response(camera.model_dump(mode="json"), message="Camera deactivated")
