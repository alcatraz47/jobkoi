"""Frontend state models for master profile editing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExperienceEntry:
    """Editable experience item for frontend profile forms."""

    company: str = ""
    title: str = ""
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


@dataclass
class SkillEntry:
    """Editable skill item for frontend profile forms."""

    skill_name: str = ""
    level: str | None = None
    category: str | None = None


@dataclass
class EducationEntry:
    """Editable education item for frontend profile forms."""

    institution: str = ""
    degree: str = ""
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class AcademicAchievementEntry:
    """Editable academic achievement item for frontend profile forms."""

    title: str = ""
    achievement_type: str = ""
    institution: str | None = None
    year: str | None = None
    description: str | None = None


@dataclass
class ProjectEntry:
    """Editable project item for frontend profile forms."""

    name: str = ""
    role: str | None = None
    technologies: str | None = None
    description: str | None = None
    outcome: str | None = None


@dataclass
class CertificationEntry:
    """Editable certification item for frontend profile forms."""

    name: str = ""
    issuer: str | None = None
    issue_date: str | None = None
    credential_id: str | None = None


@dataclass
class LanguageProficiencyEntry:
    """Editable language proficiency item for frontend profile forms."""

    language: str = ""
    proficiency: str = ""


@dataclass
class JobPreferenceEntry:
    """Editable job preference item for frontend profile forms."""

    preferred_titles: str | None = None
    preferred_locations: str | None = None
    work_mode: str | None = None


@dataclass
class MasterProfileDraft:
    """Complete editable master profile draft used by frontend state."""

    full_name: str = ""
    email: str = ""
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str | None = None
    experiences: list[ExperienceEntry] = field(default_factory=list)
    skills: list[SkillEntry] = field(default_factory=list)
    educations: list[EducationEntry] = field(default_factory=list)
    academic_achievements: list[AcademicAchievementEntry] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    certifications: list[CertificationEntry] = field(default_factory=list)
    languages: list[LanguageProficiencyEntry] = field(default_factory=list)
    job_preferences: list[JobPreferenceEntry] = field(default_factory=list)


@dataclass
class ProfileState:
    """State container for profile page editing context."""

    draft: MasterProfileDraft = field(default_factory=MasterProfileDraft)
    profile_id: str | None = None
    active_version_id: str | None = None

    def load_from_profile_response(self, payload: dict[str, Any]) -> None:
        """Load frontend state from backend profile response payload.

        Args:
            payload: Profile response payload returned by backend API.
        """

        active_version = payload.get("active_version", {})
        self.profile_id = payload.get("profile_id")
        self.active_version_id = active_version.get("version_id")
        self.draft = MasterProfileDraft(
            full_name=str(active_version.get("full_name", "")),
            email=str(active_version.get("email", "")),
            phone=_none_or_str(active_version.get("phone")),
            location=_none_or_str(active_version.get("location")),
            headline=_none_or_str(active_version.get("headline")),
            summary=_none_or_str(active_version.get("summary")),
            experiences=[
                ExperienceEntry(
                    company=str(item.get("company", "")),
                    title=str(item.get("title", "")),
                    start_date=_none_or_str(item.get("start_date")),
                    end_date=_none_or_str(item.get("end_date")),
                    description=_none_or_str(item.get("description")),
                )
                for item in active_version.get("experiences", [])
            ],
            educations=[
                EducationEntry(
                    institution=str(item.get("institution", "")),
                    degree=str(item.get("degree", "")),
                    field_of_study=_none_or_str(item.get("field_of_study")),
                    start_date=_none_or_str(item.get("start_date")),
                    end_date=_none_or_str(item.get("end_date")),
                )
                for item in active_version.get("educations", [])
            ],
            skills=[
                SkillEntry(
                    skill_name=str(item.get("skill_name", "")),
                    level=_none_or_str(item.get("level")),
                    category=_none_or_str(item.get("category")),
                )
                for item in active_version.get("skills", [])
            ],
        )

    def to_backend_payload(self) -> dict[str, Any]:
        """Map frontend draft state to backend profile request payload.

        Returns:
            Dictionary aligned with backend profile create/update schemas.
        """

        return {
            "full_name": self.draft.full_name,
            "email": self.draft.email,
            "phone": self.draft.phone,
            "location": self.draft.location,
            "headline": self.draft.headline,
            "summary": self.draft.summary,
            "experiences": [asdict(item) for item in self.draft.experiences],
            "educations": [asdict(item) for item in self.draft.educations],
            "skills": [asdict(item) for item in self.draft.skills],
        }

    def completeness_summary(self) -> dict[str, int]:
        """Compute basic profile completeness summary for dashboard cards.

        Returns:
            Count summary across core profile categories.
        """

        return {
            "experiences": len(self.draft.experiences),
            "skills": len(self.draft.skills),
            "educations": len(self.draft.educations),
            "academic_achievements": len(self.draft.academic_achievements),
            "projects": len(self.draft.projects),
            "certifications": len(self.draft.certifications),
            "languages": len(self.draft.languages),
        }


def _none_or_str(value: Any) -> str | None:
    """Return string representation for optional values.

    Args:
        value: Any input value.

    Returns:
        String value or None.
    """

    if value is None:
        return None
    text = str(value)
    return text if text else None
