"""Pydantic DTOs. ORM models are never exposed directly."""

from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead
from app.schemas.camera import CameraCreate, CameraDetailRead, CameraRead, CameraUpdate
from app.schemas.common import MessageResponse, ORMModel, PaginationQuery
from app.schemas.detection import (
    AlertAckRequest,
    AlertRead,
    DetectionFilter,
    DetectionRead,
    WorkerEventIngest,
)
from app.schemas.statistics import (
    CameraCount,
    CountByKey,
    DetectionStatistics,
    StatisticsSummary,
    TimeBucket,
    ZoneCount,
)
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneUpdate

__all__ = [
    "AlertAckRequest",
    "AlertRead",
    "CameraCount",
    "CameraCreate",
    "CameraDetailRead",
    "CameraRead",
    "CameraUpdate",
    "CountByKey",
    "DetectionFilter",
    "DetectionRead",
    "DetectionStatistics",
    "LoginRequest",
    "MessageResponse",
    "ORMModel",
    "PaginationQuery",
    "StatisticsSummary",
    "TimeBucket",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "WorkerEventIngest",
    "ZoneCount",
    "ZoneCreate",
    "ZoneRead",
    "ZoneUpdate",
]
