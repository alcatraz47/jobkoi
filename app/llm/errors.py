"""Error types for local LLM integration."""

from __future__ import annotations


class LlmError(Exception):
    """Base error for LLM module failures."""


class LlmTransportError(LlmError):
    """Raised when HTTP communication with Ollama fails."""


class LlmResponseFormatError(LlmError):
    """Raised when model output cannot be parsed into expected structure."""
