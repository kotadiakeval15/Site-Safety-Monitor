"""Camera CRUD and worker-lifecycle business logic."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.enums import SEVERITY_TO_LINE, CameraStatus, SourceType
from app.exceptions.base import NotFoundError, ValidationError, WorkerError
from app.models.camera import Camera
from app.repositories.audit_repo import AuditRepository
from app.repositories.camera_repo import CameraRepository
from app.schemas.camera import CameraCreate, CameraDetailRead, CameraUpdate
from app.utils.video import normalize_uploaded_video
from app.workers.messages import WorkerConfig, WorkerLineConfig
from app.workers.supervisor import WorkerSupervisor, get_supervisor

logger = get_logger(__name__)

_ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
_UPLOAD_CHUNK = 1024 * 1024


def _package_torch_dir(source_dir: Path, target_file: Path) -> str:
    """Repack an extracted ``best/`` torch archive into a loadable ``.pt`` zip."""

    import zipfile

    target_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target_file, "w", compression=zipfile.ZIP_STORED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                arcname = Path("best") / file_path.relative_to(source_dir)
                zf.write(file_path, arcname.as_posix())
    return str(target_file)


def _resolve_helmet_model_path(configured: str | None) -> str | None:
    """Locate the helmet weights file used by live helmet detection."""

    candidates = [
        configured,
        "models/best.pt",
        "models/helmet_yolov8.pt",
    ]
    seen: set[str] = set()
    for raw in candidates:
        if not raw or raw in seen:
            continue
        seen.add(raw)
        path = Path(raw)
        if path.is_file():
            logger.info("Using helmet model file %s", path)
            return str(path)
        inner = path / "best" if (path / "best" / "data.pkl").exists() else path
        if inner.is_dir() and (inner / "data.pkl").exists():
            packaged = Path(get_settings().data_dir) / "models_cache" / "best.pt"
            if not packaged.is_file() or packaged.stat().st_mtime < inner.stat().st_mtime:
                logger.info("Packaging extracted helmet model from %s -> %s", inner, packaged)
                _package_torch_dir(inner, packaged)
            return str(packaged)
    logger.warning("Helmet model not found in %s; helmet mode runs without helmet weights", list(seen))
    return None


class CameraService:
    """CRUD for cameras plus activation of AI background workers."""

    def __init__(self, session: AsyncSession, supervisor: WorkerSupervisor | None = None) -> None:
        self._session = session
        self._cameras = CameraRepository(session)
        self._audit = AuditRepository(session)
        self._supervisor = supervisor or get_supervisor()

    async def list_cameras(self) -> list[CameraDetailRead]:
        cameras = await self._cameras.list_all()
        return [self._to_detail(c) for c in cameras]

    async def get_camera(self, camera_id: UUID) -> CameraDetailRead:
        camera = await self._require(camera_id)
        return self._to_detail(camera)

    async def create_camera(self, payload: CameraCreate, actor_id: UUID) -> CameraDetailRead:
        camera = Camera(
            name=payload.name,
            source_type=payload.source_type,
            stream_url=payload.stream_url,
            status=CameraStatus.INACTIVE,
        )
        await self._cameras.add(camera)
        await self._audit.record("camera.create", actor_id, {"camera_id": str(camera.camera_id)})
        camera = await self._require(camera.camera_id)
        return self._to_detail(camera)

    async def update_camera(
        self, camera_id: UUID, payload: CameraUpdate, actor_id: UUID
    ) -> CameraDetailRead:
        camera = await self._require(camera_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(camera, field, value)
        await self._session.flush()
        await self._audit.record("camera.update", actor_id, {"camera_id": str(camera_id), **data})
        camera = await self._require(camera_id)
        return self._to_detail(camera)

    async def upload_video(
        self, camera_id: UUID, file: UploadFile, actor_id: UUID
    ) -> CameraDetailRead:
        """Store an uploaded video and point the camera source at it."""

        camera = await self._require(camera_id)
        settings = get_settings()
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in _ALLOWED_VIDEO_SUFFIXES:
            raise ValidationError(
                f"Unsupported video format '{suffix or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_VIDEO_SUFFIXES))}"
            )

        os.makedirs(settings.uploads_dir, exist_ok=True)
        uploads_dir = Path(settings.uploads_dir)
        # Always stage under a distinct name so ffmpeg never overwrites in-place.
        temp_target = uploads_dir / f"{camera_id}_upload{suffix}"

        max_bytes = settings.max_upload_mb * 1024 * 1024
        written = 0
        with temp_target.open("wb") as out:
            while chunk := await file.read(_UPLOAD_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    temp_target.unlink(missing_ok=True)
                    raise ValidationError(f"Video exceeds the {settings.max_upload_mb} MB limit")
                out.write(chunk)

        # WhatsApp / phone clips are often AV1 — transcode to H.264 for OpenCV.
        final_path = normalize_uploaded_video(temp_target, str(camera_id), uploads_dir)

        camera.source_type = SourceType.FILE
        camera.stream_url = str(final_path)
        await self._session.flush()
        await self._audit.record(
            "camera.video_upload",
            actor_id,
            {"camera_id": str(camera_id), "path": str(final_path), "bytes": written},
        )
        camera = await self._require(camera_id)
        return self._to_detail(camera)

    async def delete_camera(self, camera_id: UUID, actor_id: UUID) -> None:
        camera = await self._require(camera_id)
        self._supervisor.deactivate(str(camera_id))
        await self._cameras.delete(camera)
        await self._audit.record("camera.delete", actor_id, {"camera_id": str(camera_id)})

    async def activate_camera(self, camera_id: UUID, actor_id: UUID) -> CameraDetailRead:
        camera = await self._require(camera_id)
        config = self._build_worker_config(camera)
        try:
            self._supervisor.activate(config)
        except WorkerError:
            camera.status = CameraStatus.ERROR
            await self._session.flush()
            raise
        camera.status = CameraStatus.ACTIVE
        await self._session.flush()
        await self._audit.record("camera.activate", actor_id, {"camera_id": str(camera_id)})
        return self._to_detail(camera)

    async def deactivate_camera(self, camera_id: UUID, actor_id: UUID) -> CameraDetailRead:
        camera = await self._require(camera_id)
        self._supervisor.deactivate(str(camera_id))
        camera.status = CameraStatus.INACTIVE
        await self._session.flush()
        await self._audit.record("camera.deactivate", actor_id, {"camera_id": str(camera_id)})
        return self._to_detail(camera)

    def _build_worker_config(self, camera: Camera) -> WorkerConfig:
        settings = get_settings()
        lines: list[WorkerLineConfig] = []
        for zone in camera.zones:
            if not zone.is_active:
                continue
            color = SEVERITY_TO_LINE[zone.severity].value
            # Use the oriented segment when defined; otherwise fall back to a
            # horizontal, full-width line at ``line_y``.
            x1 = zone.line_x1 if zone.line_x1 is not None else 0.0
            y1 = zone.line_y1 if zone.line_y1 is not None else zone.line_y
            x2 = zone.line_x2 if zone.line_x2 is not None else 1.0
            y2 = zone.line_y2 if zone.line_y2 is not None else zone.line_y
            lines.append(
                WorkerLineConfig(
                    color=color,
                    severity=zone.severity.value,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    zone_id=str(zone.zone_id),
                )
            )
        # Restricted-area lines are derived strictly from the camera's active
        # safety zones. No zones means no lines (nothing to cross).
        # Only pass the helmet model when the weights actually exist, otherwise
        # ultralytics raises on load and the worker dies immediately (which the
        # UI would then report as an inactive camera).
        helmet_path = _resolve_helmet_model_path(settings.helmet_model_path or None)
        return WorkerConfig(
            camera_id=str(camera.camera_id),
            stream_url=camera.stream_url,
            lines=lines,
            yolo_model_path=settings.yolo_model_path,
            helmet_model_path=helmet_path,
            confidence=settings.confidence_threshold,
            device=settings.inference_device,
            frame_skip=settings.frame_skip,
            cooldown_seconds=settings.alert_cooldown_seconds,
            live_frames_dir=settings.live_frames_dir,
            show_window=settings.worker_show_window,
            detection_mode=camera.detection_mode.value,
        )

    def _to_detail(self, camera: Camera) -> CameraDetailRead:
        detail = CameraDetailRead.model_validate(camera)
        # Reflect real worker liveness in the reported status.
        if camera.status == CameraStatus.ACTIVE and not self._supervisor.is_running(
            str(camera.camera_id)
        ):
            detail.status = CameraStatus.INACTIVE
        detail.has_video = (
            camera.source_type == SourceType.FILE
            and bool(camera.stream_url)
            and os.path.isfile(camera.stream_url)
        )
        return detail

    async def _require(self, camera_id: UUID) -> Camera:
        camera = await self._cameras.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera not found")
        return camera
