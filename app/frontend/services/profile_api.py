"""Profile-focused frontend API adapter."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class ProfileApi:
    """Adapter for profile CRUD and profile version endpoints."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize profile API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def get_profile(self) -> dict[str, Any]:
        """Fetch active master profile.

        Returns:
            Profile response payload.
        """

        return self._client.get_json("/profile")

    def create_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create singleton master profile.

        Args:
            payload: Profile create payload.

        Returns:
            Created profile payload.
        """

        return self._client.post_json("/profile", payload)

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update profile by creating a new active version.

        Args:
            payload: Profile update payload.

        Returns:
            Updated profile payload.
        """

        return self._client.put_json("/profile", payload)

    def list_versions(self) -> dict[str, Any]:
        """List stored profile versions.

        Returns:
            Profile version listing payload.
        """

        return self._client.get_json("/profile/versions")
