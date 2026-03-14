"""Profile CRUD and versioning API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.profile import (
    DeleteProfileResponse,
    MasterProfileCreateRequest,
    MasterProfileResponse,
    MasterProfileUpdateRequest,
    MasterProfileVersionListResponse,
    MasterProfileVersionResponse,
)
from app.services.profile_service import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileService,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=MasterProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    request: MasterProfileCreateRequest,
    session: Session = Depends(get_db_session),
) -> MasterProfileResponse:
    """Create the singleton master profile.

    Args:
        request: Profile creation payload.
        session: Database session dependency.

    Returns:
        Created profile with active version.

    Raises:
        HTTPException: On duplicate profile creation.
    """

    service = ProfileService(session)
    try:
        return service.create_profile(request)
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=MasterProfileResponse)
def get_profile(session: Session = Depends(get_db_session)) -> MasterProfileResponse:
    """Get the active master profile.

    Args:
        session: Database session dependency.

    Returns:
        Active profile response.

    Raises:
        HTTPException: When profile is missing.
    """

    service = ProfileService(session)
    try:
        return service.get_profile()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("", response_model=MasterProfileResponse)
def update_profile(
    request: MasterProfileUpdateRequest,
    session: Session = Depends(get_db_session),
) -> MasterProfileResponse:
    """Update profile by appending a new active version.

    Args:
        request: Profile update payload.
        session: Database session dependency.

    Returns:
        Updated active profile response.

    Raises:
        HTTPException: When profile is missing.
    """

    service = ProfileService(session)
    try:
        return service.update_profile(request)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("", response_model=DeleteProfileResponse)
def delete_profile(session: Session = Depends(get_db_session)) -> DeleteProfileResponse:
    """Delete the singleton master profile.

    Args:
        session: Database session dependency.

    Returns:
        Deletion acknowledgement.

    Raises:
        HTTPException: When profile is missing.
    """

    service = ProfileService(session)
    try:
        return service.delete_profile()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/versions", response_model=MasterProfileVersionListResponse)
def list_profile_versions(session: Session = Depends(get_db_session)) -> MasterProfileVersionListResponse:
    """List all profile versions.

    Args:
        session: Database session dependency.

    Returns:
        Ordered profile version list.

    Raises:
        HTTPException: When profile is missing.
    """

    service = ProfileService(session)
    try:
        return service.list_profile_versions()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/versions/{version_id}", response_model=MasterProfileVersionResponse)
def get_profile_version(
    version_id: str,
    session: Session = Depends(get_db_session),
) -> MasterProfileVersionResponse:
    """Get a specific profile version.

    Args:
        version_id: Profile version identifier.
        session: Database session dependency.

    Returns:
        Requested profile version.

    Raises:
        HTTPException: When profile or version is missing.
    """

    service = ProfileService(session)
    try:
        return service.get_profile_version(version_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
