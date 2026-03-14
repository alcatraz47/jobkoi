"""Health check API router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response payload for health checks.

    Attributes:
        status: Current service health status.
        app_name: Logical application name.
        environment: Runtime environment name.
        timestamp_utc: UTC timestamp for response generation.
    """

    status: str = Field(default="ok")
    app_name: str
    environment: str
    timestamp_utc: datetime


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return a basic liveness response.

    Returns:
        Standardized health response payload.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        timestamp_utc=datetime.now(timezone.utc),
    )
