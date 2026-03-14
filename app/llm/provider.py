"""Cached provider for Ollama client instances."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.llm.client import OllamaClient, OllamaClientSettings


@lru_cache(maxsize=1)
def get_ollama_client(
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> OllamaClient:
    """Return a cached Ollama client instance.

    Args:
        base_url: Optional Ollama base URL override.
        model: Optional model name override.
        timeout_seconds: Optional request timeout override in seconds.
        max_retries: Optional retry attempts after initial call.

    Returns:
        Cached Ollama client instance.
    """

    settings = get_settings()
    client_settings = OllamaClientSettings(
        base_url=base_url or settings.ollama_base_url,
        model=model or settings.ollama_model,
        timeout_seconds=timeout_seconds
        if timeout_seconds is not None
        else settings.ollama_timeout_seconds,
        max_retries=max_retries if max_retries is not None else settings.ollama_max_retries,
    )
    return OllamaClient(settings=client_settings)
