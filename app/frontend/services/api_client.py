"""HTTP client adapter for frontend-to-backend API communication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class FrontendApiError(Exception):
    """Raised when backend API requests fail in frontend adapters."""


@dataclass(frozen=True)
class ApiClient:
    """Thin typed HTTP client wrapper for backend API access."""

    base_url: str
    timeout_seconds: float = 20.0

    def get_json(self, path: str) -> dict[str, Any]:
        """Execute a GET request and parse JSON object response.

        Args:
            path: Relative API path.

        Returns:
            Parsed JSON object.

        Raises:
            FrontendApiError: If request fails.
        """

        return self._request_json("GET", path)

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a POST request with JSON payload.

        Args:
            path: Relative API path.
            payload: JSON body payload.

        Returns:
            Parsed JSON object.

        Raises:
            FrontendApiError: If request fails.
        """

        return self._request_json("POST", path, payload)

    def put_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a PUT request with JSON payload.

        Args:
            path: Relative API path.
            payload: JSON body payload.

        Returns:
            Parsed JSON object.

        Raises:
            FrontendApiError: If request fails.
        """

        return self._request_json("PUT", path, payload)

    def delete_json(self, path: str) -> dict[str, Any]:
        """Execute a DELETE request and parse JSON object response.

        Args:
            path: Relative API path.

        Returns:
            Parsed JSON object.

        Raises:
            FrontendApiError: If request fails.
        """

        return self._request_json("DELETE", path)

    def get_text(self, path: str) -> str:
        """Execute a GET request and return text response body.

        Args:
            path: Relative API path.

        Returns:
            Response body text.

        Raises:
            FrontendApiError: If request fails.
        """

        url = self.build_download_url(path)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            raise FrontendApiError(f"Failed to contact backend API: {exc}") from exc

        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise FrontendApiError(f"API request failed ({response.status_code}): {detail}")
        return response.text

    def build_download_url(self, path: str) -> str:
        """Build absolute download URL for browser link targets.

        Args:
            path: Relative API path.

        Returns:
            Absolute URL.
        """

        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and parse object JSON response.

        Args:
            method: HTTP method.
            path: Relative API path.
            payload: Optional JSON body.

        Returns:
            Parsed JSON object.

        Raises:
            FrontendApiError: If HTTP request or JSON parse fails.
        """

        url = self.build_download_url(path)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(method=method, url=url, json=payload)
        except httpx.HTTPError as exc:
            raise FrontendApiError(f"Failed to contact backend API: {exc}") from exc

        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            raise FrontendApiError(f"API request failed ({response.status_code}): {detail}")

        try:
            parsed = response.json()
        except ValueError as exc:
            raise FrontendApiError("Backend returned non-JSON response.") from exc

        if not isinstance(parsed, dict):
            raise FrontendApiError("Backend JSON response must be an object.")
        return parsed


def build_default_api_client() -> ApiClient:
    """Build API client from current runtime settings.

    Returns:
        Configured API client.
    """

    settings = get_settings()
    host = settings.app_host if settings.app_host != "0.0.0.0" else "127.0.0.1"
    base_url = f"http://{host}:{settings.app_port}/api/v1"
    return ApiClient(base_url=base_url)


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract readable error detail from API responses.

    Args:
        response: HTTP response object.

    Returns:
        Error detail text.
    """

    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unknown error"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail is not None:
            return str(detail)
    return str(payload)
