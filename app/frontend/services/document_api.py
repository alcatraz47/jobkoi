"""Document generation and retrieval frontend API adapter."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class DocumentApi:
    """Adapter for CV and cover letter generation endpoints."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize document API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def generate_cv(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate CV artifacts for a snapshot.

        Args:
            payload: Document generation payload.

        Returns:
            Generation payload containing artifacts.
        """

        return self._client.post_json("/documents/cv", payload)

    def generate_cover_letter(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate cover letter artifacts for a snapshot.

        Args:
            payload: Document generation payload.

        Returns:
            Generation payload containing artifacts.
        """

        return self._client.post_json("/documents/cover-letter", payload)

    def list_snapshot_documents(self, snapshot_id: str) -> dict[str, Any]:
        """List generated artifacts for one snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Artifact list payload.
        """

        return self._client.get_json(f"/documents/snapshots/{snapshot_id}")

    def get_document_metadata(self, artifact_id: str) -> dict[str, Any]:
        """Fetch metadata for one generated artifact.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Artifact metadata payload.
        """

        return self._client.get_json(f"/documents/{artifact_id}")

    def get_document_text(self, artifact_id: str) -> str:
        """Download text content for one document artifact.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Downloaded text body.
        """

        return self._client.get_text(f"/documents/{artifact_id}/download")

    def build_download_url(self, artifact_id: str) -> str:
        """Build browser download URL for an artifact.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Absolute download URL.
        """

        return self._client.build_download_url(f"/documents/{artifact_id}/download")
