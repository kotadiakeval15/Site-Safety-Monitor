"""SQLAlchemy ORM models.

Importing this package registers every model on the shared metadata, which is
required by Alembic autogenerate and ``Base.metadata.create_all``.
"""

from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.base import Base, TimestampMixin, utcnow
from app.models.camera import Camera
from app.models.detection import Detection
from app.models.user import User
from app.models.zone import Zone

__all__ = [
    "Alert",
    "AuditLog",
    "Base",
    "Camera",
    "Detection",
    "TimestampMixin",
    "User",
    "Zone",
    "utcnow",
]
