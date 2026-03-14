"""API routes for structured job analysis operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.job import JobAnalysisCreateRequest, JobAnalysisResponse
from app.services.job_analysis_service import JobAnalysisNotFoundError, JobAnalysisService
from app.services.job_post_service import JobPostNotFoundError

router = APIRouter(tags=["job-analyses"])


@router.post("/job-posts/{job_post_id}/analyses", response_model=JobAnalysisResponse, status_code=201)
def analyze_job_post(
    job_post_id: str,
    request: JobAnalysisCreateRequest,
    session: Session = Depends(get_db_session),
) -> JobAnalysisResponse:
    """Create and persist a structured analysis for a job post.

    Args:
        job_post_id: Job post identifier.
        request: Analysis request payload.
        session: Database session dependency.

    Returns:
        Persisted job analysis response.

    Raises:
        HTTPException: If job post is missing.
    """

    service = JobAnalysisService(session)
    try:
        return service.analyze_job_post(job_post_id=job_post_id, request=request)
    except JobPostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/job-posts/{job_post_id}/analyses/latest", response_model=JobAnalysisResponse)
def get_latest_analysis_for_job_post(
    job_post_id: str,
    session: Session = Depends(get_db_session),
) -> JobAnalysisResponse:
    """Get the latest analysis for a job post.

    Args:
        job_post_id: Job post identifier.
        session: Database session dependency.

    Returns:
        Latest job analysis response.

    Raises:
        HTTPException: If job post or analysis is missing.
    """

    service = JobAnalysisService(session)
    try:
        return service.get_latest_for_job_post(job_post_id)
    except JobPostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobAnalysisNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/job-analyses/{analysis_id}", response_model=JobAnalysisResponse)
def get_analysis(
    analysis_id: str,
    session: Session = Depends(get_db_session),
) -> JobAnalysisResponse:
    """Get a structured analysis by identifier.

    Args:
        analysis_id: Analysis identifier.
        session: Database session dependency.

    Returns:
        Analysis response.

    Raises:
        HTTPException: If analysis is missing.
    """

    service = JobAnalysisService(session)
    try:
        return service.get_analysis(analysis_id)
    except JobAnalysisNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
