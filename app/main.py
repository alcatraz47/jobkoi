"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers.application_packages import router as application_packages_router
from app.api.routers.documents import router as documents_router
from app.api.routers.health import router as health_router
from app.api.routers.job_analyses import router as job_analysis_router
from app.api.routers.job_posts import router as job_post_router
from app.api.routers.profile import router as profile_router
from app.api.routers.profile_imports import router as profile_import_router
from app.api.routers.tailoring import router as tailoring_router
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import dispose_engine

try:
    from app.frontend.ui import register_frontend
except Exception:  # pragma: no cover - optional frontend import guard
    register_frontend = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Args:
        _: FastAPI application instance.

    Yields:
        None.
    """

    settings: Settings = get_settings()
    setup_logging(settings.app_log_level)
    logger = get_logger(__name__)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)

    yield

    dispose_engine()
    logger.info("Stopped %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """

    settings: Settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(profile_router, prefix="/api/v1")
    app.include_router(profile_import_router, prefix="/api/v1")
    app.include_router(job_post_router, prefix="/api/v1")
    app.include_router(job_analysis_router, prefix="/api/v1")
    app.include_router(tailoring_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(application_packages_router, prefix="/api/v1")

    if register_frontend is not None:
        register_frontend(app)

    return app


app = create_app()
