"""Application package frontend API adapter."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class ApplicationPackageApi:
    """Adapter for reproducible application package endpoints."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize application package API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def create_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create application package.

        Args:
            payload: Package create payload.

        Returns:
            Created package payload.
        """

        return self._client.post_json("/application-packages", payload)

    def list_packages(self) -> dict[str, Any]:
        """List stored application packages.

        Returns:
            Package list payload.
        """

        return self._client.get_json("/application-packages")

    def get_package(self, package_id: str) -> dict[str, Any]:
        """Fetch one application package.

        Args:
            package_id: Package identifier.

        Returns:
            Package payload.
        """

        return self._client.get_json(f"/application-packages/{package_id}")
