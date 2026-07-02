"""Alert ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import AlertLevel
from app.models.base import Base, utcnow
from app.models.types import enum_column

if TYPE_CHECKING:
    from app.models.detection import Detection


class Alert(Base):
    """An operator-facing alert derived from a detection."""

    __tablename__ = "alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    detection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("detections.detection_id", ondelete="CASCADE"), index=True, nullable=False
    )
    level: Mapped[AlertLevel] = mapped_column(enum_column(AlertLevel), nullable=False)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    acked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    detection: Mapped[Detection] = relationship(back_populates="alert", lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Alert {self.level} ack={self.acknowledged}>"
