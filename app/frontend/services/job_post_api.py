"""Job intake and analysis frontend API adapter."""

from __future__ import annotations

from typing import Any

from app.frontend.services.api_client import ApiClient, build_default_api_client


class JobPostApi:
    """Adapter for job post submission and analysis endpoints."""

    def __init__(self, client: ApiClient | None = None) -> None:
        """Initialize job post API adapter.

        Args:
            client: Optional shared API client.
        """

        self._client = client or build_default_api_client()

    def create_job_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create job post from title and description.

        Args:
            payload: Job post create payload.

        Returns:
            Stored job post payload.
        """

        return self._client.post_json("/job-posts", payload)

    def get_job_post(self, job_post_id: str) -> dict[str, Any]:
        """Fetch one job post.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Job post payload.
        """

        return self._client.get_json(f"/job-posts/{job_post_id}")

    def analyze_job_post(self, job_post_id: str, *, use_llm: bool = False) -> dict[str, Any]:
        """Run structured analysis for one job post.

        Args:
            job_post_id: Job post identifier.
            use_llm: Optional LLM extraction toggle.

        Returns:
            Job analysis payload.
        """

        return self._client.post_json(f"/job-posts/{job_post_id}/analyses", {"use_llm": use_llm})

    def get_latest_analysis(self, job_post_id: str) -> dict[str, Any]:
        """Fetch latest analysis for one job post.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Latest analysis payload.
        """

        return self._client.get_json(f"/job-posts/{job_post_id}/analyses/latest")
