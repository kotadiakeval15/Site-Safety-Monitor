"""Safety zone ORM model.

A zone promotes the previous per-camera line configuration into a first-class
entity. Each zone defines one severity line at ``line_y`` (fraction of frame
height) bound to a camera.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ZoneSeverity
from app.models.base import Base, TimestampMixin
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.camera import Camera


class Zone(Base, TimestampMixin):
    """A safety line/zone bound to a camera with a severity level."""

    __tablename__ = "zones"

    zone_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cameras.camera_id", ondelete="CASCADE"), index=True, nullable=False
    )
    severity: Mapped[ZoneSeverity] = mapped_column(enum_column(ZoneSeverity), nullable=False)
    line_y: Mapped[float] = mapped_column(Float, nullable=False)
    # Optional oriented line segment (normalized 0..1). When present these define
    # the line drawn on the floor; otherwise the line is horizontal at ``line_y``.
    line_x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    line_y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    line_x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    line_y2: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="zones")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Zone {self.name} {self.severity}@{self.line_y}>"
