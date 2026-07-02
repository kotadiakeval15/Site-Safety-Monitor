"""Camera ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import CameraStatus, DetectionMode, SourceType
from app.models.base import Base, TimestampMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.detection import Detection
    from app.models.zone import Zone


class Camera(Base, TimestampMixin):
    """A camera source that can be activated for live monitoring."""

    __tablename__ = "cameras"

    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType), nullable=False)
    stream_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CameraStatus] = mapped_column(
        enum_column(CameraStatus), default=CameraStatus.INACTIVE, nullable=False
    )
    detection_mode: Mapped[DetectionMode] = mapped_column(
        enum_column(DetectionMode),
        default=DetectionMode.RESTRICTED_AREA,
        server_default=DetectionMode.RESTRICTED_AREA.value,
        nullable=False,
    )

    zones: Mapped[list[Zone]] = relationship(
        back_populates="camera", cascade="all, delete-orphan", lazy="selectin"
    )
    detections: Mapped[list[Detection]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Camera {self.name} ({self.status})>"
