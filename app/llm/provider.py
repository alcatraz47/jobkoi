"""Cached provider for Ollama client instances."""

from __future__ import annotations

from functools import lru_cache

from app.llm.client import OllamaClient, OllamaClientSettings


@lru_cache(maxsize=1)
def get_ollama_client(
    *,
    base_url: str = "http://127.0.0.1:11434",
    model: str = "qwen2.5:3b-instruct",
    timeout_seconds: float = 30.0,
    max_retries: int = 1,
) -> OllamaClient:
    """Return a cached Ollama client instance.

    Args:
        base_url: Ollama base URL.
        model: Model name configured in local Ollama.
        timeout_seconds: Request timeout in seconds.
        max_retries: Number of retry attempts after initial call.

    Returns:
        Cached Ollama client instance.
    """

    settings = OllamaClientSettings(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    return OllamaClient(settings=settings)
