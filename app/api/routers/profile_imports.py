"""API routes for CV and portfolio website profile imports."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db_session, get_session_factory
from app.schemas.profile_import import (
    ProfileImportApplyResponse,
    ProfileImportDeleteResponse,
    ProfileImportRejectRequest,
    ProfileImportReviewRequest,
    ProfileImportRunListResponse,
    ProfileImportRunResponse,
    WebsiteImportRequest,
)
from app.services.profile_import_extractors import ProfileImportExtractionError
from app.services.profile_import_service import (
    ProfileImportRunNotFoundError,
    ProfileImportService,
    ProfileImportValidationError,
)

router = APIRouter(prefix="/profile-imports", tags=["profile-imports"])
logger = get_logger(__name__)


def _process_queued_cv_import_run(run_id: str) -> None:
    """Process one queued CV import run in a background task.

    Args:
        run_id: Import run identifier.
    """

    session = get_session_factory()()
    try:
        service = ProfileImportService(session)
        service.process_queued_cv_run(run_id)
    except Exception:
        logger.exception("Queued CV import processing failed for run_id=%s", run_id)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()


@router.post("/cv/async", response_model=ProfileImportRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_cv_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Queue a profile import run from uploaded CV file.

    Args:
        background_tasks: FastAPI background task registry.
        file: Uploaded CV file payload.
        session: Database session dependency.

    Returns:
        Queued import run response.

    Raises:
        HTTPException: If file validation fails.
    """

    content = await file.read()
    service = ProfileImportService(session)
    try:
        run_response = await run_in_threadpool(
            service.enqueue_cv_import,
            file_name=file.filename or "uploaded_cv",
            content_type=file.content_type,
            file_bytes=content,
        )
    except ProfileImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    background_tasks.add_task(_process_queued_cv_import_run, run_response.id)
    return run_response


@router.post("/cv", response_model=ProfileImportRunResponse, status_code=status.HTTP_201_CREATED)
async def import_cv(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Create a profile import run from uploaded CV file.

    Args:
        file: Uploaded CV file payload.
        session: Database session dependency.

    Returns:
        Created import run response.

    Raises:
        HTTPException: If file validation or extraction fails.
    """

    content = await file.read()
    service = ProfileImportService(session)
    try:
        return await run_in_threadpool(
            service.import_cv,
            file_name=file.filename or "uploaded_cv",
            content_type=file.content_type,
            file_bytes=content,
        )
    except ProfileImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except ProfileImportExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/website", response_model=ProfileImportRunResponse, status_code=status.HTTP_201_CREATED)
def import_website(
    request: WebsiteImportRequest,
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Create a profile import run from a portfolio website URL.

    Args:
        request: Website import request payload.
        session: Database session dependency.

    Returns:
        Created import run response.

    Raises:
        HTTPException: If extraction fails.
    """

    service = ProfileImportService(session)
    try:
        return service.import_website(request)
    except ProfileImportExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("", response_model=ProfileImportRunListResponse)
def list_profile_import_runs(
    session: Session = Depends(get_db_session),
) -> ProfileImportRunListResponse:
    """List profile import runs.

    Args:
        session: Database session dependency.

    Returns:
        Import run list response.
    """

    service = ProfileImportService(session)
    return service.list_runs()


@router.get("/{run_id}", response_model=ProfileImportRunResponse)
def get_profile_import_run(
    run_id: str,
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Get one profile import run by identifier.

    Args:
        run_id: Import run identifier.
        session: Database session dependency.

    Returns:
        Import run response.

    Raises:
        HTTPException: If run does not exist.
    """

    service = ProfileImportService(session)
    try:
        return service.get_run(run_id)
    except ProfileImportRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{run_id}/review", response_model=ProfileImportRunResponse)
def review_profile_import_run(
    run_id: str,
    request: ProfileImportReviewRequest,
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Apply review decisions to one profile import run.

    Args:
        run_id: Import run identifier.
        request: Review decisions payload.
        session: Database session dependency.

    Returns:
        Updated import run response.

    Raises:
        HTTPException: If run is missing or payload is invalid.
    """

    service = ProfileImportService(session)
    try:
        return service.review_run(run_id, request)
    except ProfileImportRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProfileImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{run_id}/apply", response_model=ProfileImportApplyResponse)
def apply_profile_import_run(
    run_id: str,
    session: Session = Depends(get_db_session),
) -> ProfileImportApplyResponse:
    """Apply reviewed import fields into master profile version history.

    Args:
        run_id: Import run identifier.
        session: Database session dependency.

    Returns:
        Apply response containing updated run and profile.

    Raises:
        HTTPException: If run is missing or apply validation fails.
    """

    service = ProfileImportService(session)
    try:
        return service.apply_run(run_id)
    except ProfileImportRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProfileImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.delete("/{run_id}", response_model=ProfileImportDeleteResponse)
def delete_profile_import_run(
    run_id: str,
    session: Session = Depends(get_db_session),
) -> ProfileImportDeleteResponse:
    """Delete one profile import run.

    Args:
        run_id: Import run identifier.
        session: Database session dependency.

    Returns:
        Deletion acknowledgement payload.

    Raises:
        HTTPException: If run is missing.
    """

    service = ProfileImportService(session)
    try:
        return service.delete_run(run_id)
    except ProfileImportRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{run_id}/reject", response_model=ProfileImportRunResponse)
def reject_profile_import_run(
    run_id: str,
    request: ProfileImportRejectRequest,
    session: Session = Depends(get_db_session),
) -> ProfileImportRunResponse:
    """Reject one import run.

    Args:
        run_id: Import run identifier.
        request: Reject payload.
        session: Database session dependency.

    Returns:
        Updated import run response.

    Raises:
        HTTPException: If run is missing.
    """

    service = ProfileImportService(session)
    try:
        return service.reject_run(run_id, request)
    except ProfileImportRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
