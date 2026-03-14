"""Service for job post ingestion operations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.job import JobPostModel
from app.db.repositories.job_repository import JobPostCreatePayload, JobPostRepository
from app.domain.job_text import detect_language_fallback, normalize_text
from app.schemas.job import JobPostCreateRequest, JobPostResponse


class JobPostNotFoundError(Exception):
    """Raised when a requested job post cannot be found."""


class JobPostService:
    """Service coordinating job post submission and retrieval."""

    def __init__(self, session: Session) -> None:
        """Initialize service with persistence dependencies.

        Args:
            session: Active database session.
        """

        self._session = session
        self._repository = JobPostRepository(session)

    def create_job_post(self, request: JobPostCreateRequest) -> JobPostResponse:
        """Create a job post from raw title and description text.

        Args:
            request: Job post request payload.

        Returns:
            Stored job post response.
        """

        normalized_title = normalize_text(request.title)
        normalized_description = normalize_text(request.description)
        detected_language = detect_language_fallback(
            f"{normalized_title} {normalized_description}",
            default_language="en",
        )

        payload = JobPostCreatePayload(
            title=normalized_title,
            company=request.company,
            description_raw=request.description,
            normalized_description=normalized_description,
            detected_language=detected_language,
        )
        model = self._repository.create(payload)
        self._session.commit()
        return self._to_response(model)

    def get_job_post(self, job_post_id: str) -> JobPostResponse:
        """Fetch one job post by identifier.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Job post response payload.

        Raises:
            JobPostNotFoundError: If the job post does not exist.
        """

        model = self._repository.get(job_post_id)
        if model is None:
            raise JobPostNotFoundError("Job post not found.")
        return self._to_response(model)

    @staticmethod
    def _to_response(model: JobPostModel) -> JobPostResponse:
        """Map job post ORM model to API response schema.

        Args:
            model: Persisted job post ORM instance.

        Returns:
            Job post response schema.
        """

        return JobPostResponse(
            id=model.id,
            title=model.title,
            company=model.company,
            description_raw=model.description_raw,
            normalized_description=model.normalized_description,
            detected_language=model.detected_language,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
