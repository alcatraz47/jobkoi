"""API routes for reproducible application package operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.application_package import (
    ApplicationPackageCreateRequest,
    ApplicationPackageListResponse,
    ApplicationPackageResponse,
)
from app.services.application_package_service import (
    ApplicationPackageDependencyError,
    ApplicationPackageNotFoundError,
    ApplicationPackageService,
    ApplicationPackageValidationError,
)

router = APIRouter(prefix="/application-packages", tags=["application-packages"])


@router.post("", response_model=ApplicationPackageResponse, status_code=status.HTTP_201_CREATED)
def create_application_package(
    request: ApplicationPackageCreateRequest,
    session: Session = Depends(get_db_session),
) -> ApplicationPackageResponse:
    """Create a new reproducible application package.

    Args:
        request: Package creation payload.
        session: Database session dependency.

    Returns:
        Created package response.

    Raises:
        HTTPException: If dependencies are missing or linkage validation fails.
    """

    service = ApplicationPackageService(session)
    try:
        return service.create_package(request)
    except ApplicationPackageDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ApplicationPackageValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("", response_model=ApplicationPackageListResponse)
def list_application_packages(
    session: Session = Depends(get_db_session),
) -> ApplicationPackageListResponse:
    """List stored application packages.

    Args:
        session: Database session dependency.

    Returns:
        Package list response.
    """

    service = ApplicationPackageService(session)
    return service.list_packages()


@router.get("/{package_id}", response_model=ApplicationPackageResponse)
def get_application_package(
    package_id: str,
    session: Session = Depends(get_db_session),
) -> ApplicationPackageResponse:
    """Retrieve one application package by identifier.

    Args:
        package_id: Package identifier.
        session: Database session dependency.

    Returns:
        Package response.

    Raises:
        HTTPException: If package does not exist.
    """

    service = ApplicationPackageService(session)
    try:
        return service.get_package(package_id)
    except ApplicationPackageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
