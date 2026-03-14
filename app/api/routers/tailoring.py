"""API routes for tailoring plans and tailored snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.tailoring import (
    TailoredSnapshotCreateRequest,
    TailoredSnapshotResponse,
    TailoringPlanCreateRequest,
    TailoringPlanResponse,
)
from app.services.tailoring_service import (
    TailoringDependencyNotFoundError,
    TailoringPlanNotFoundError,
    TailoringService,
    TailoringSnapshotNotFoundError,
    TailoringValidationError,
)

router = APIRouter(prefix="/tailoring", tags=["tailoring"])


@router.post("/plans", response_model=TailoringPlanResponse, status_code=status.HTTP_201_CREATED)
def create_tailoring_plan(
    request: TailoringPlanCreateRequest,
    session: Session = Depends(get_db_session),
) -> TailoringPlanResponse:
    """Create a deterministic tailoring plan.

    Args:
        request: Tailoring plan creation payload.
        session: Database session dependency.

    Returns:
        Created tailoring plan.

    Raises:
        HTTPException: If source profile version or analysis is missing.
    """

    service = TailoringService(session)
    try:
        return service.create_tailoring_plan(request)
    except TailoringDependencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/plans/{plan_id}", response_model=TailoringPlanResponse)
def get_tailoring_plan(
    plan_id: str,
    session: Session = Depends(get_db_session),
) -> TailoringPlanResponse:
    """Get one tailoring plan by identifier.

    Args:
        plan_id: Tailoring plan identifier.
        session: Database session dependency.

    Returns:
        Requested tailoring plan.

    Raises:
        HTTPException: If the plan is missing.
    """

    service = TailoringService(session)
    try:
        return service.get_tailoring_plan(plan_id)
    except TailoringPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/snapshots", response_model=TailoredSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    request: TailoredSnapshotCreateRequest,
    session: Session = Depends(get_db_session),
) -> TailoredSnapshotResponse:
    """Create a tailored profile snapshot from a tailoring plan.

    Args:
        request: Snapshot creation payload.
        session: Database session dependency.

    Returns:
        Created tailored snapshot.

    Raises:
        HTTPException: If dependencies are missing or factual guards fail.
    """

    service = TailoringService(session)
    try:
        return service.create_snapshot(request)
    except TailoringPlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TailoringDependencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TailoringValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}", response_model=TailoredSnapshotResponse)
def get_snapshot(
    snapshot_id: str,
    session: Session = Depends(get_db_session),
) -> TailoredSnapshotResponse:
    """Get one tailored profile snapshot.

    Args:
        snapshot_id: Snapshot identifier.
        session: Database session dependency.

    Returns:
        Requested tailored snapshot.

    Raises:
        HTTPException: If snapshot is missing.
    """

    service = TailoringService(session)
    try:
        return service.get_snapshot(snapshot_id)
    except TailoringSnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
