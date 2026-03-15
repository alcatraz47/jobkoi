"""HTTP client wrapper for local Ollama model interactions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.llm.errors import LlmResponseFormatError, LlmTransportError
from app.llm.parser import parse_structured_output

TModel = TypeVar("TModel", bound=BaseModel)
TReturn = TypeVar("TReturn")


@dataclass(frozen=True)
class OllamaClientSettings:
    """Configuration values for Ollama client behavior.

    Attributes:
        base_url: Ollama base URL.
        model: Model name configured in local Ollama.
        timeout_seconds: Request timeout in seconds.
        max_retries: Number of retry attempts after the initial request.
    """

    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:4b"
    timeout_seconds: float = 120.0
    max_retries: int = 1


class OllamaClient:
    """Typed wrapper around the Ollama HTTP API."""

    def __init__(
        self,
        settings: OllamaClientSettings,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Initialize an Ollama client wrapper.

        Args:
            settings: Runtime configuration values.
            http_client: Optional preconfigured HTTP client for tests.
        """

        self._settings = settings
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=settings.timeout_seconds)

    def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Generate plain text from the model.

        Args:
            prompt: User prompt text.
            system_prompt: System instruction text.
            temperature: Sampling temperature.

        Returns:
            Model response text.

        Raises:
            LlmTransportError: If transport-level errors occur.
        """

        return self._call_with_retries(
            operation=lambda: self._chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                structured=False,
            )
        )

    def generate_structured(
        self,
        *,
        prompt: str,
        system_prompt: str,
        schema: type[TModel],
        temperature: float = 0.0,
    ) -> TModel:
        """Generate structured JSON output and validate it.

        Args:
            prompt: User prompt text.
            system_prompt: System instruction text.
            schema: Pydantic schema expected in response.
            temperature: Sampling temperature.

        Returns:
            Parsed and validated schema instance.

        Raises:
            LlmTransportError: If transport-level errors occur.
            LlmResponseFormatError: If output cannot be parsed into schema.
        """

        def operation() -> TModel:
            raw = self._chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                structured=True,
            )
            return parse_structured_output(raw, schema)

        return self._call_with_retries(operation=operation)

    def get_server_version(self) -> str:
        """Fetch Ollama server version.

        Returns:
            Ollama version string.

        Raises:
            LlmTransportError: If Ollama is unreachable or returns invalid payload.
        """

        decoded = self._request_json("GET", "/api/version")
        version = decoded.get("version")
        if not isinstance(version, str) or not version.strip():
            raise LlmTransportError("Ollama version response is missing 'version'.")
        return version.strip()

    def is_model_available(self) -> bool:
        """Return whether configured model is available in Ollama.

        Returns:
            True when model exists, otherwise False.

        Raises:
            LlmTransportError: If transport fails or unexpected HTTP status is returned.
        """

        endpoint = f"{self._settings.base_url.rstrip('/')}/api/show"
        payload = {"model": self._settings.model}
        try:
            response = self._http_client.post(endpoint, json=payload)
        except httpx.HTTPError as exc:
            raise LlmTransportError(f"Failed to contact Ollama: {exc}") from exc

        if response.status_code == 404:
            return False

        if response.status_code >= 400:
            raise LlmTransportError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        return True

    def warmup_model(self) -> str:
        """Warm up the configured model with a lightweight call.

        Returns:
            Model response text.

        Raises:
            LlmTransportError: If warm-up call cannot be completed.
        """

        return self.generate_text(
            prompt="Reply with OK.",
            system_prompt="Respond with OK only.",
            temperature=0.0,
        )

    def close(self) -> None:
        """Close underlying HTTP resources."""

        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> OllamaClient:
        """Enter context manager.

        Returns:
            This client instance.
        """

        return self

    def __exit__(self, *_: object) -> None:
        """Exit context manager and close owned resources."""

        self.close()

    def _call_with_retries(self, operation: Callable[[], TReturn]) -> TReturn:
        """Execute operation with simple retry handling.

        Args:
            operation: Callable operation to execute.

        Returns:
            Operation result.

        Raises:
            LlmTransportError: If all retries fail due transport issues.
            LlmResponseFormatError: If all retries fail due parsing issues.
        """

        attempts = self._settings.max_retries + 1
        last_error: Exception | None = None

        for attempt_index in range(attempts):
            try:
                return operation()
            except (LlmTransportError, LlmResponseFormatError) as exc:
                last_error = exc
                if attempt_index == attempts - 1:
                    raise

        assert last_error is not None
        raise last_error

    def _chat(
        self,
        *,
        prompt: str,
        system_prompt: str,
        temperature: float,
        structured: bool,
    ) -> str:
        """Send chat request to local Ollama API.

        Args:
            prompt: User prompt text.
            system_prompt: System instruction text.
            temperature: Sampling temperature.
            structured: Enables JSON mode when True.

        Returns:
            Response content string.

        Raises:
            LlmTransportError: If HTTP or response parsing fails.
        """

        payload: dict[str, object] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if structured:
            payload["format"] = "json"

        try:
            response = self._http_client.post(
                f"{self._settings.base_url.rstrip('/')}/api/chat",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise LlmTransportError(f"Failed to contact Ollama: {exc}") from exc

        if response.status_code >= 400:
            raise LlmTransportError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        try:
            decoded = response.json()
        except ValueError as exc:
            raise LlmTransportError("Ollama response is not valid JSON envelope.") from exc

        message = decoded.get("message")
        if not isinstance(message, dict):
            raise LlmTransportError("Ollama response missing 'message' object.")

        content = message.get("content")
        if not isinstance(content, str):
            raise LlmTransportError("Ollama response missing text content.")

        return content.strip()

    def _request_json(self, method: str, path: str) -> dict[str, object]:
        """Execute request and decode JSON object response.

        Args:
            method: HTTP method.
            path: Relative Ollama API path.

        Returns:
            JSON object payload.

        Raises:
            LlmTransportError: If request fails or response is not a JSON object.
        """

        endpoint = f"{self._settings.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = self._http_client.request(method=method, url=endpoint)
        except httpx.HTTPError as exc:
            raise LlmTransportError(f"Failed to contact Ollama: {exc}") from exc

        if response.status_code >= 400:
            raise LlmTransportError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        try:
            decoded = response.json()
        except ValueError as exc:
            raise LlmTransportError("Ollama response is not valid JSON.") from exc

        if not isinstance(decoded, dict):
            raise LlmTransportError("Ollama response JSON must be an object.")
        return decoded
