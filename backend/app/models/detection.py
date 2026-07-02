"""Unified detection ORM model.

Replaces the previous ``helmet_events`` and ``line_crossing_events`` tables with
a single table that powers both the Detection feed and the Statistics feature.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import CrossedLine, ViolationType, ZoneSeverity
from app.models.base import Base, utcnow
from app.models.types import JSONColumn, enum_column

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.camera import Camera


class Detection(Base):
    """A single safety violation detected by a camera worker."""

    __tablename__ = "detections"

    detection_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cameras.camera_id", ondelete="CASCADE"), index=True, nullable=False
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("zones.zone_id", ondelete="SET NULL"), index=True, nullable=True
    )
    worker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    violation_type: Mapped[ViolationType] = mapped_column(
        enum_column(ViolationType), index=True, nullable=False
    )
    severity: Mapped[ZoneSeverity] = mapped_column(enum_column(ZoneSeverity), nullable=False)
    crossed_line: Mapped[CrossedLine | None] = mapped_column(
        enum_column(CrossedLine), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    bbox: Mapped[list[int] | None] = mapped_column(JSONColumn, nullable=True)
    foot_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    foot_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    camera: Mapped[Camera] = relationship(back_populates="detections")
    alert: Mapped[Alert | None] = relationship(
        back_populates="detection", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Detection {self.violation_type} cam={self.camera_id} worker={self.worker_id}>"
