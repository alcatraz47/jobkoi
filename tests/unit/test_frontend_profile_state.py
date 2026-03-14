"""Unit tests for frontend profile state mappings."""

from __future__ import annotations

from app.frontend.state.profile_state import (
    AcademicAchievementEntry,
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    LanguageProficiencyEntry,
    ProfileState,
    ProjectEntry,
    SkillEntry,
)


def test_profile_state_loads_active_profile_payload() -> None:
    """Profile state should map backend active profile payload into draft values."""

    state = ProfileState()
    state.load_from_profile_response(
        {
            "profile_id": "profile-1",
            "active_version": {
                "version_id": "version-1",
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "phone": "+49 123",
                "location": "Berlin",
                "headline": "Backend Engineer",
                "summary": "Builds reliable systems.",
                "experiences": [
                    {
                        "company": "ACME",
                        "title": "Engineer",
                        "start_date": "2020-01-01",
                        "end_date": None,
                        "description": "Built APIs.",
                    }
                ],
                "educations": [
                    {
                        "institution": "TU Berlin",
                        "degree": "MSc",
                        "field_of_study": "Computer Science",
                        "start_date": "2017-01-01",
                        "end_date": "2019-01-01",
                    }
                ],
                "skills": [
                    {
                        "skill_name": "Python",
                        "level": "advanced",
                        "category": "backend",
                    }
                ],
            },
        }
    )

    assert state.profile_id == "profile-1"
    assert state.active_version_id == "version-1"
    assert state.draft.full_name == "Ada Lovelace"
    assert state.draft.experiences[0].company == "ACME"
    assert state.draft.educations[0].degree == "MSc"
    assert state.draft.skills[0].skill_name == "Python"


def test_profile_state_backend_payload_includes_supported_sections() -> None:
    """Backend payload mapper should include profile core sections."""

    state = ProfileState()
    state.draft.full_name = "Grace Hopper"
    state.draft.email = "grace@example.com"
    state.draft.experiences = [ExperienceEntry(company="Navy", title="Rear Admiral")]
    state.draft.educations = [EducationEntry(institution="Yale", degree="PhD")]
    state.draft.skills = [SkillEntry(skill_name="COBOL")]

    payload = state.to_backend_payload()

    assert payload["full_name"] == "Grace Hopper"
    assert payload["email"] == "grace@example.com"
    assert payload["experiences"][0]["company"] == "Navy"
    assert payload["educations"][0]["institution"] == "Yale"
    assert payload["skills"][0]["skill_name"] == "COBOL"


def test_profile_state_completeness_summary_counts_all_frontend_sections() -> None:
    """Completeness summary should count frontend-only and backend-supported sections."""

    state = ProfileState()
    state.draft.experiences = [ExperienceEntry(), ExperienceEntry()]
    state.draft.skills = [SkillEntry()]
    state.draft.educations = [EducationEntry()]
    state.draft.academic_achievements = [AcademicAchievementEntry()]
    state.draft.projects = [ProjectEntry()]
    state.draft.certifications = [CertificationEntry()]
    state.draft.languages = [LanguageProficiencyEntry()]

    summary = state.completeness_summary()

    assert summary == {
        "experiences": 2,
        "skills": 1,
        "educations": 1,
        "academic_achievements": 1,
        "projects": 1,
        "certifications": 1,
        "languages": 1,
    }
