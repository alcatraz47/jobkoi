"""Tailoring and snapshot frontend API adapter."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class TailoringApi:
    """Adapter for tailoring plan and snapshot endpoints."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize tailoring API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create tailoring plan.

        Args:
            payload: Tailoring plan create payload.

        Returns:
            Tailoring plan payload.
        """

        return self._client.post_json("/tailoring/plans", payload)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        """Fetch one tailoring plan.

        Args:
            plan_id: Plan identifier.

        Returns:
            Tailoring plan payload.
        """

        return self._client.get_json(f"/tailoring/plans/{plan_id}")

    def create_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create tailored snapshot.

        Args:
            payload: Snapshot create payload.

        Returns:
            Snapshot payload.
        """

        return self._client.post_json("/tailoring/snapshots", payload)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Fetch one tailored snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Snapshot payload.
        """

        return self._client.get_json(f"/tailoring/snapshots/{snapshot_id}")
