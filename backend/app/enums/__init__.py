"""Centralized enumerations shared across the application.

Every domain enum lives here so that models, schemas, services and the AI
workers all reference a single source of truth.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum whose members serialize to their value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class Role(StrEnum):
    """Role-based access control roles ordered from most to least privileged."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    VIEWER = "viewer"


class SourceType(StrEnum):
    """Supported camera stream source types."""

    CCTV = "cctv"
    IP = "ip"
    WEBCAM = "webcam"
    MOBILE = "mobile"
    FILE = "file"


class CameraStatus(StrEnum):
    """Lifecycle state of a camera and its background worker."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    ERROR = "error"


class DetectionMode(StrEnum):
    """Which single safety use-case a camera's worker evaluates."""

    RESTRICTED_AREA = "restricted_area"
    HELMET = "helmet"


class ZoneSeverity(StrEnum):
    """Severity of a safety zone / line."""

    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    DANGER = "danger"


class ViolationType(StrEnum):
    """Type of safety violation captured as a detection."""

    HELMET_VIOLATION = "helmet_violation"
    LINE_CROSSING = "line_crossing"


class CrossedLine(StrEnum):
    """Color of the safety line a worker crossed."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class AlertLevel(StrEnum):
    """Escalation level of an alert derived from a detection."""

    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    DANGER = "danger"


# Mapping helpers -----------------------------------------------------------

SEVERITY_TO_LINE: dict[ZoneSeverity, CrossedLine] = {
    ZoneSeverity.LEVEL_1: CrossedLine.GREEN,
    ZoneSeverity.LEVEL_2: CrossedLine.YELLOW,
    ZoneSeverity.DANGER: CrossedLine.RED,
}

LINE_TO_SEVERITY: dict[CrossedLine, ZoneSeverity] = {
    line: severity for severity, line in SEVERITY_TO_LINE.items()
}

LINE_TO_ALERT_LEVEL: dict[CrossedLine, AlertLevel] = {
    CrossedLine.GREEN: AlertLevel.LEVEL_1,
    CrossedLine.YELLOW: AlertLevel.LEVEL_2,
    CrossedLine.RED: AlertLevel.DANGER,
}

ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 1,
    Role.ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}


def role_at_least(role: Role, minimum: Role) -> bool:
    """Return True if ``role`` is at least as privileged as ``minimum``."""

    return ROLE_RANK[role] >= ROLE_RANK[minimum]


__all__ = [
    "StrEnum",
    "Role",
    "SourceType",
    "CameraStatus",
    "DetectionMode",
    "ZoneSeverity",
    "ViolationType",
    "CrossedLine",
    "AlertLevel",
    "SEVERITY_TO_LINE",
    "LINE_TO_SEVERITY",
    "LINE_TO_ALERT_LEVEL",
    "ROLE_RANK",
    "role_at_least",
]
