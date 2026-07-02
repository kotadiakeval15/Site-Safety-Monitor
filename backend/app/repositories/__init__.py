"""Data access layer. All DB reads/writes go through a repository."""

from app.repositories.alert_repo import AlertRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.base import BaseRepository
from app.repositories.camera_repo import CameraRepository
from app.repositories.detection_repo import DetectionRepository
from app.repositories.statistics_repo import StatisticsRepository
from app.repositories.user_repo import UserRepository
from app.repositories.zone_repo import ZoneRepository

__all__ = [
    "AlertRepository",
    "AuditRepository",
    "BaseRepository",
    "CameraRepository",
    "DetectionRepository",
    "StatisticsRepository",
    "UserRepository",
    "ZoneRepository",
]
