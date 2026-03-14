"""Unit tests for profile service behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.schemas.profile import MasterProfileCreateRequest, MasterProfileUpdateRequest
from app.services.profile_service import ProfileAlreadyExistsError, ProfileNotFoundError, ProfileService


def make_create_request(summary: str) -> MasterProfileCreateRequest:
    """Build a sample profile creation request.

    Args:
        summary: Summary field value.

    Returns:
        Sample profile create request payload.
    """

    return MasterProfileCreateRequest(
        full_name="Arfan Example",
        email="arfan@example.com",
        phone="+49 123 4567",
        location="Berlin",
        headline="Backend Engineer",
        summary=summary,
        experiences=[
            {
                "company": "Example GmbH",
                "title": "Software Engineer",
                "description": "Built APIs.",
            }
        ],
        educations=[
            {
                "institution": "TU Example",
                "degree": "MSc",
                "field_of_study": "Computer Science",
            }
        ],
        skills=[{"skill_name": "Python", "level": "advanced", "category": "programming"}],
    )


def test_service_creates_and_versions_profile(db_session: Session) -> None:
    """Service should create first version then append a new version on update."""

    service = ProfileService(db_session)

    created = service.create_profile(make_create_request("Initial summary"))
    assert created.active_version.version_number == 1
    assert created.active_version.summary == "Initial summary"

    update_request = MasterProfileUpdateRequest(**make_create_request("Updated summary").model_dump())
    updated = service.update_profile(update_request)

    assert updated.active_version.version_number == 2
    assert updated.active_version.summary == "Updated summary"

    versions = service.list_profile_versions()
    assert [item.version_number for item in versions.versions] == [2, 1]

    older_version = service.get_profile_version(versions.versions[-1].version_id)
    assert older_version.summary == "Initial summary"


def test_service_rejects_duplicate_profile_creation(db_session: Session) -> None:
    """Service should reject creating a second singleton profile."""

    service = ProfileService(db_session)
    service.create_profile(make_create_request("Summary"))

    with pytest.raises(ProfileAlreadyExistsError):
        service.create_profile(make_create_request("Another"))


def test_service_raises_not_found_when_profile_missing(db_session: Session) -> None:
    """Service should fail with not found when profile does not exist."""

    service = ProfileService(db_session)

    with pytest.raises(ProfileNotFoundError):
        service.get_profile()
