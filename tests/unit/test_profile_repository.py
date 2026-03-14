"""Unit tests for profile repository behavior."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.profile_repository import (
    EducationPayload,
    ExperiencePayload,
    ProfileRepository,
    ProfileVersionPayload,
    SkillPayload,
)


def build_payload(summary: str) -> ProfileVersionPayload:
    """Build a sample profile version payload.

    Args:
        summary: Summary text to include.

    Returns:
        A repository profile version payload.
    """

    return ProfileVersionPayload(
        full_name="Arfan Example",
        email="arfan@example.com",
        phone="+49 123 4567",
        location="Berlin",
        headline="Python Engineer",
        summary=summary,
        experiences=[
            ExperiencePayload(
                company="Example GmbH",
                title="Software Engineer",
                start_date=None,
                end_date=None,
                description="Built internal tools.",
            )
        ],
        educations=[
            EducationPayload(
                institution="TU Example",
                degree="MSc",
                field_of_study="Computer Science",
                start_date=None,
                end_date=None,
            )
        ],
        skills=[SkillPayload(skill_name="Python", level="advanced", category="programming")],
    )


def test_repository_creates_profile_and_first_version(db_session: Session) -> None:
    """Repository should persist master profile and associated version rows."""

    repository = ProfileRepository(db_session)

    profile = repository.create_profile()
    version = repository.create_profile_version(profile.id, build_payload("Initial summary"))
    repository.set_active_version(profile, version.id)
    db_session.commit()

    loaded = repository.get_profile()
    assert loaded is not None
    assert loaded.active_version_id == version.id

    stored_version = repository.get_profile_version(profile.id, version.id)
    assert stored_version is not None
    assert stored_version.version_number == 1
    assert stored_version.summary == "Initial summary"
    assert len(stored_version.experiences) == 1
    assert len(stored_version.educations) == 1
    assert len(stored_version.skills) == 1


def test_repository_increments_version_number(db_session: Session) -> None:
    """Repository should allocate sequential version numbers."""

    repository = ProfileRepository(db_session)
    profile = repository.create_profile()

    version_1 = repository.create_profile_version(profile.id, build_payload("V1"))
    repository.set_active_version(profile, version_1.id)

    version_2 = repository.create_profile_version(profile.id, build_payload("V2"))
    repository.set_active_version(profile, version_2.id)
    db_session.commit()

    versions = repository.list_profile_versions(profile.id)
    assert [item.version_number for item in versions] == [2, 1]
    assert repository.get_next_version_number(profile.id) == 3
