"""Frontend adapter for profile import API routes."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class ProfileImportApi:
    """Adapter for CV and website import routes."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize profile import API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def import_cv(self, *, file_name: str, file_bytes: bytes, content_type: str) -> dict[str, Any]:
        """Create import run from uploaded CV bytes.

        Args:
            file_name: Uploaded file name.
            file_bytes: Uploaded file bytes.
            content_type: Uploaded MIME type.

        Returns:
            Import run payload.
        """

        return self._client.post_multipart(
            "/profile-imports/cv",
            {
                "file": (file_name, file_bytes, content_type),
            },
        )

    def import_website(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create import run from website URL request payload."""

        return self._client.post_json("/profile-imports/website", payload)

    def list_runs(self) -> dict[str, Any]:
        """List profile import runs."""

        return self._client.get_json("/profile-imports")

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Fetch one profile import run."""

        return self._client.get_json(f"/profile-imports/{run_id}")

    def review_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit review decisions for one import run."""

        return self._client.post_json(f"/profile-imports/{run_id}/review", payload)

    def apply_run(self, run_id: str) -> dict[str, Any]:
        """Apply approved import fields to master profile."""

        return self._client.post_json(f"/profile-imports/{run_id}/apply", {})

    def delete_run(self, run_id: str) -> dict[str, Any]:
        """Delete one import run and remove it from listing."""

        return self._client.delete_json(f"/profile-imports/{run_id}")

    def reject_run(self, run_id: str, note: str | None = None) -> dict[str, Any]:
        """Reject import run and keep master profile unchanged."""

        return self._client.post_json(
            f"/profile-imports/{run_id}/reject",
            {"note": note},
        )
