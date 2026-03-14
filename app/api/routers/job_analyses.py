"""API routes for structured job analysis operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.llm.errors import LlmResponseFormatError, LlmTransportError
from app.llm.extraction_helper import ExtractionHelper, OllamaJobAnalysisAdapter
from app.llm.provider import get_ollama_client
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
        HTTPException: If job post is missing or LLM integration fails.
    """

    service = _build_job_analysis_service(session=session, use_llm=request.use_llm)
    try:
        return service.analyze_job_post(job_post_id=job_post_id, request=request)
    except JobPostNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LlmTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service unavailable: {exc}",
        ) from exc
    except LlmResponseFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned invalid structured output: {exc}",
        ) from exc


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


def _build_job_analysis_service(*, session: Session, use_llm: bool) -> JobAnalysisService:
    """Build job analysis service with optional Ollama-backed adapter.

    Args:
        session: Active database session.
        use_llm: Whether the caller requested LLM assistance.

    Returns:
        Configured job analysis service instance.
    """

    if not use_llm:
        return JobAnalysisService(session)

    client = get_ollama_client()
    helper = ExtractionHelper(client)
    adapter = OllamaJobAnalysisAdapter(helper)
    return JobAnalysisService(session, llm_adapter=adapter)
