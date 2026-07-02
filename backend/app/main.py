"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.core.request_context import get_request_id, new_request_id, set_request_id
from app.exceptions import register_exception_handlers
from app.responses import success_response
from app.services.auth_service import AuthService
from app.workers.event_drainer import EventDrainer
from app.workers.supervisor import get_supervisor

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown: logging, seeding, workers, drainer."""

    setup_logging()
    logger.info("Starting %s", get_settings().app_name)

    async with AsyncSessionLocal() as session:
        try:
            await AuthService(session).seed_admin_if_needed()
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Admin seeding failed (is the database migrated?)")

    supervisor = get_supervisor()
    drainer = EventDrainer(supervisor.event_queue)
    drainer.start()
    app.state.supervisor = supervisor
    app.state.drainer = drainer

    yield

    logger.info("Shutting down")
    await drainer.stop()
    supervisor.shutdown()


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-grade construction site safety monitoring platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = get_request_id()
        return response

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/", tags=["root"])
    async def root() -> dict:
        return success_response(
            {"service": "construction-site-safety-backend", "docs": "/docs"},
            message="Construction Site Safety API",
        )

    return app


app = create_app()
