"""Application configuration loaded from a single ``.env`` file.

All runtime configuration flows through :class:`Settings`. Nothing in the code
base should read ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application ------------------------------------------------------
    app_name: str = "Construction Site Safety API"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # -- Database ---------------------------------------------------------
    database_url: str = (
        "postgresql+asyncpg://safety_admin:safety_secret_change_me"
        "@localhost:5432/construction_safety"
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # -- JWT / security ---------------------------------------------------
    jwt_secret_key: str = "change-this-to-a-long-random-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # -- Seed super admin -------------------------------------------------
    admin_name: str = "Super Admin"
    admin_email: str = "admin@safety.com"
    admin_password: str = "Admin@123456"

    # -- Server -----------------------------------------------------------
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # -- Rate limiting ----------------------------------------------------
    rate_limit_default: str = "120/minute"
    rate_limit_login: str = "10/minute"
    rate_limit_enabled: bool = True

    # -- Storage / logging ------------------------------------------------
    data_dir: str = "/data"
    screenshots_dir: str = "/data/screenshots"
    uploads_dir: str = "/data/uploads"
    logs_dir: str = "/data/logs"
    live_frames_dir: str = "/data/live"
    log_level: str = "INFO"

    # -- AI / worker configuration ---------------------------------------
    yolo_model_path: str = "yolov8n.pt"
    helmet_model_path: str = "models/best.pt"
    confidence_threshold: float = 0.45
    inference_device: str = "cpu"
    frame_skip: int = 2
    max_active_cameras: int = 8
    alert_cooldown_seconds: float = 10.0
    # Open a native OpenCV preview window inside each worker process. Requires a
    # display and is disabled by default (has no effect in headless containers).
    worker_show_window: bool = False
    max_upload_mb: int = 512

    # -- Default safety line positions (fraction of frame height) --------
    green_line_y: float = 0.55
    yellow_line_y: float = 0.45
    red_line_y: float = 0.35

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a clean list."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()
