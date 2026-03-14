"""Domain data structures for tailoring plan and snapshot generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProfileExperienceFact:
    """Profile experience fact used by pure tailoring logic.

    Attributes:
        id: Source experience identifier.
        company: Company name.
        title: Role title.
        start_date: Optional start date.
        end_date: Optional end date.
        description: Optional role description.
    """

    id: str
    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None


@dataclass(frozen=True)
class ProfileEducationFact:
    """Profile education fact used by pure tailoring logic."""

    id: str
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class ProfileSkillFact:
    """Profile skill fact used by pure tailoring logic."""

    id: str
    skill_name: str
    level: str | None
    category: str | None


@dataclass(frozen=True)
class ProfileVersionData:
    """Master profile version data projected for deterministic tailoring.

    Attributes:
        id: Profile version identifier.
        full_name: Candidate full name.
        email: Candidate email.
        phone: Candidate phone.
        location: Candidate location.
        headline: Optional profile headline.
        summary: Optional profile summary.
        experiences: Experience facts.
        educations: Education facts.
        skills: Skill facts.
    """

    id: str
    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    experiences: list[ProfileExperienceFact]
    educations: list[ProfileEducationFact]
    skills: list[ProfileSkillFact]


@dataclass(frozen=True)
class JobRequirementData:
    """Job requirement data used in matching and scoring."""

    id: str
    text: str
    requirement_type: str
    is_must_have: bool
    priority_score: int


@dataclass(frozen=True)
class JobAnalysisData:
    """Structured job analysis data for tailoring.

    Attributes:
        id: Job analysis identifier.
        detected_language: Language code.
        requirements: Extracted requirements.
    """

    id: str
    detected_language: str
    requirements: list[JobRequirementData]


@dataclass(frozen=True)
class TailoringPlanFactDraft:
    """Draft fact entry generated for a tailoring plan."""

    fact_key: str
    fact_type: str
    source_entity_id: str | None
    text: str
    relevance_score: int
    is_selected: bool
    selection_reason: str


@dataclass(frozen=True)
class TailoringPlanDraft:
    """Deterministic tailoring plan draft."""

    profile_version_id: str
    job_analysis_id: str
    target_language: str
    summary: str
    facts: list[TailoringPlanFactDraft]


@dataclass(frozen=True)
class SnapshotExperienceDraft:
    """Experience entry in a tailored snapshot."""

    source_experience_id: str | None
    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None
    relevance_score: int


@dataclass(frozen=True)
class SnapshotEducationDraft:
    """Education entry in a tailored snapshot."""

    source_education_id: str | None
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    relevance_score: int


@dataclass(frozen=True)
class SnapshotSkillDraft:
    """Skill entry in a tailored snapshot."""

    source_skill_id: str | None
    skill_name: str
    level: str | None
    category: str | None
    relevance_score: int


@dataclass(frozen=True)
class ProfileSnapshotDraft:
    """Tailored snapshot draft copied from selected master profile facts."""

    profile_version_id: str
    target_language: str
    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    experiences: list[SnapshotExperienceDraft]
    educations: list[SnapshotEducationDraft]
    skills: list[SnapshotSkillDraft]
