"""Unit tests for frontend API client wrapper."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.frontend.services.api_client import ApiClient, FrontendApiError


class FakeResponse:
    """Simple fake response object for API client tests."""

    def __init__(
        self,
        *,
        status_code: int,
        payload: Any | None = None,
        text: str = "",
    ) -> None:
        """Initialize fake response values.

        Args:
            status_code: HTTP status code.
            payload: JSON payload value.
            text: Text payload.
        """

        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        """Return configured JSON payload."""

        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class FakeHttpxClient:
    """Context-manager fake for ``httpx.Client``."""

    def __init__(self, *, response: FakeResponse) -> None:
        """Initialize with one static response.

        Args:
            response: Fake response returned by all methods.
        """

        self._response = response

    def __enter__(self) -> FakeHttpxClient:
        """Enter context manager."""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit context manager."""

        return None

    def request(
        self,
        *,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> FakeResponse:
        """Return fake response for request API."""

        _ = (method, url, json)
        return self._response

    def get(self, url: str) -> FakeResponse:
        """Return fake response for GET API."""

        _ = url
        return self._response


class FakeHttpxFactory:
    """Factory replacing ``httpx.Client`` constructor."""

    def __init__(self, response: FakeResponse) -> None:
        """Store response used by produced fake clients."""

        self._response = response

    def __call__(self, timeout: float) -> FakeHttpxClient:
        """Return fake client instance.

        Args:
            timeout: Requested timeout.

        Returns:
            Fake HTTP client.
        """

        _ = timeout
        return FakeHttpxClient(response=self._response)


def test_api_client_get_json_returns_dictionary(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET JSON should return parsed dictionary payload."""

    monkeypatch.setattr(
        httpx,
        "Client",
        FakeHttpxFactory(FakeResponse(status_code=200, payload={"ok": True})),
    )
    client = ApiClient(base_url="http://localhost:8000/api/v1")

    response = client.get_json("/health")

    assert response == {"ok": True}


def test_api_client_get_text_returns_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET text should return plain response text."""

    monkeypatch.setattr(
        httpx,
        "Client",
        FakeHttpxFactory(FakeResponse(status_code=200, payload=None, text="hello")),
    )
    client = ApiClient(base_url="http://localhost:8000/api/v1")

    response = client.get_text("/documents/1/download")

    assert response == "hello"


def test_api_client_raises_for_non_success_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """API client should raise frontend error for HTTP error responses."""

    monkeypatch.setattr(
        httpx,
        "Client",
        FakeHttpxFactory(
            FakeResponse(
                status_code=404,
                payload={"detail": "not found"},
            )
        ),
    )
    client = ApiClient(base_url="http://localhost:8000/api/v1")

    with pytest.raises(FrontendApiError):
        client.get_json("/missing")
