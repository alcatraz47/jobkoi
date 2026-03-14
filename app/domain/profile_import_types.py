"""Domain types for profile import extraction and review mapping."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportedExperienceDraft:
    """Structured imported experience entry draft."""

    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    source_locator: str | None = None
    source_excerpt: str | None = None


@dataclass(frozen=True)
class ImportedEducationDraft:
    """Structured imported education entry draft."""

    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source_locator: str | None = None
    source_excerpt: str | None = None


@dataclass(frozen=True)
class ImportedSkillDraft:
    """Structured imported skill entry draft."""

    skill_name: str
    level: str | None = None
    category: str | None = None
    source_locator: str | None = None
    source_excerpt: str | None = None


@dataclass(frozen=True)
class ImportedUnmappedCandidate:
    """Unmapped extraction candidate retained for reviewer visibility."""

    text: str
    section_hint: str | None = None
    reason: str | None = None
    source_locator: str | None = None


@dataclass(frozen=True)
class ImportedProfileDraft:
    """Structured imported profile draft aligned with master profile schema."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str | None = None
    experiences: list[ImportedExperienceDraft] = field(default_factory=list)
    educations: list[ImportedEducationDraft] = field(default_factory=list)
    skills: list[ImportedSkillDraft] = field(default_factory=list)
    unmapped_candidates: list[ImportedUnmappedCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class ImportFieldDraft:
    """Field-level extraction draft used in review workflow."""

    field_path: str
    section_type: str
    extracted_value: str
    suggested_value: str
    confidence_score: int
    source_locator: str | None
    source_excerpt: str | None
    sort_order: int


@dataclass(frozen=True)
class ImportConflictDraft:
    """Conflict draft comparing imported and existing profile values."""

    field_path: str
    conflict_type: str
    existing_value: str | None
    imported_value: str | None
