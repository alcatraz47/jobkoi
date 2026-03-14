"""Health check API router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.llm.errors import LlmTransportError
from app.llm.provider import get_ollama_client

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


class LlmHealthResponse(BaseModel):
    """Response payload for Ollama connectivity and model readiness checks.

    Attributes:
        status: ``ok`` when service/model checks pass, otherwise ``degraded``.
        ollama_base_url: Configured Ollama base URL.
        ollama_model: Configured Ollama model name.
        server_reachable: Whether Ollama server was reachable.
        server_version: Ollama server version when available.
        model_available: Whether configured model exists locally.
        warmed_up: Whether optional warm-up call completed successfully.
        detail: Optional error details for degraded responses.
        timestamp_utc: UTC timestamp for response generation.
    """

    status: str
    ollama_base_url: str
    ollama_model: str
    server_reachable: bool
    server_version: str | None
    model_available: bool
    warmed_up: bool
    detail: str | None
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


@router.get("/health/llm", response_model=LlmHealthResponse)
def get_llm_health(
    warmup: bool = Query(default=False),
) -> LlmHealthResponse:
    """Return Ollama server/model health and optional warm-up status.

    Args:
        warmup: When True, performs a lightweight model warm-up call.

    Returns:
        LLM health response payload.
    """

    settings = get_settings()
    client = get_ollama_client()

    server_reachable = False
    server_version: str | None = None
    model_available = False
    warmed_up = False
    detail: str | None = None

    try:
        server_version = client.get_server_version()
        server_reachable = True
        model_available = client.is_model_available()
        if warmup and model_available:
            client.warmup_model()
            warmed_up = True
    except LlmTransportError as exc:
        detail = str(exc)

    status_label = "ok"
    if not server_reachable or not model_available or (warmup and not warmed_up):
        status_label = "degraded"

    return LlmHealthResponse(
        status=status_label,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        server_reachable=server_reachable,
        server_version=server_version,
        model_available=model_available,
        warmed_up=warmed_up,
        detail=detail,
        timestamp_utc=datetime.now(timezone.utc),
    )
