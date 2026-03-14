"""API routes for job post ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.job import JobPostCreateRequest, JobPostResponse
from app.services.job_post_service import JobPostNotFoundError, JobPostService

router = APIRouter(prefix="/job-posts", tags=["job-posts"])


@router.post("", response_model=JobPostResponse, status_code=status.HTTP_201_CREATED)
def create_job_post(
    request: JobPostCreateRequest,
    session: Session = Depends(get_db_session),
) -> JobPostResponse:
    """Create a new job post from pasted title and description.

    Args:
        request: Job post creation payload.
        session: Database session dependency.

    Returns:
        Stored job post response.
    """

    service = JobPostService(session)
    return service.create_job_post(request)


@router.get("/{job_post_id}", response_model=JobPostResponse)
def get_job_post(
    job_post_id: str,
    session: Session = Depends(get_db_session),
) -> JobPostResponse:
    """Fetch one job post.

    Args:
        job_post_id: Job post identifier.
        session: Database session dependency.

    Returns:
        Job post response.

    Raises:
        HTTPException: If job post does not exist.
    """

    service = JobPostService(session)
    try:
        return service.get_job_post(job_post_id)
    except JobPostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
