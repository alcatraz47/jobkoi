"""Structured output contracts for LLM helper APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictContractModel(BaseModel):
    """Base contract model that rejects unknown keys."""

    model_config = ConfigDict(extra="forbid")


class RequirementExtractionItem(StrictContractModel):
    """One requirement extracted from a job description.

    Attributes:
        text: Human-readable requirement content.
        requirement_type: Requirement category such as ``skill`` or ``experience``.
        is_must_have: Indicates whether requirement is mandatory.
        priority_score: Relative importance in range ``0`` to ``100``.
    """

    text: str
    requirement_type: str
    is_must_have: bool
    priority_score: int = Field(ge=0, le=100)


class RequirementExtractionResponse(StrictContractModel):
    """Structured requirement extraction result.

    Attributes:
        requirements: Extracted requirement list.
    """

    requirements: list[RequirementExtractionItem] = Field(default_factory=list)


class ProfileImportScalarField(StrictContractModel):
    """Scalar profile field extracted from import text.

    Attributes:
        value: Extracted scalar value.
        source_excerpt: Optional evidence snippet from source text.
        source_locator: Optional source locator such as page label.
    """

    value: str
    source_excerpt: str | None = None
    source_locator: str | None = None


class ProfileImportExperienceItem(StrictContractModel):
    """Structured imported experience item.

    Attributes:
        company: Employer/company name.
        title: Role title.
        start_date: Optional start date string.
        end_date: Optional end date string.
        description: Optional role description.
        source_excerpt: Optional evidence snippet from source text.
        source_locator: Optional source locator such as page label.
    """

    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    source_excerpt: str | None = None
    source_locator: str | None = None


class ProfileImportEducationItem(StrictContractModel):
    """Structured imported education item.

    Attributes:
        institution: Education institution name.
        degree: Degree title.
        field_of_study: Optional field of study.
        start_date: Optional start date string.
        end_date: Optional end date string.
        source_excerpt: Optional evidence snippet from source text.
        source_locator: Optional source locator such as page label.
    """

    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source_excerpt: str | None = None
    source_locator: str | None = None


class ProfileImportSkillItem(StrictContractModel):
    """Structured imported skill item.

    Attributes:
        skill_name: Skill label.
        level: Optional skill level.
        category: Optional skill category.
        source_excerpt: Optional evidence snippet from source text.
        source_locator: Optional source locator such as page label.
    """

    skill_name: str
    level: str | None = None
    category: str | None = None
    source_excerpt: str | None = None
    source_locator: str | None = None


class ProfileImportExtractionResponse(StrictContractModel):
    """Structured imported profile extraction response.

    Attributes:
        full_name: Extracted full name field when supported.
        email: Extracted email field when supported.
        phone: Extracted phone field when supported.
        location: Extracted location field when supported.
        headline: Extracted headline field when supported.
        summary: Extracted summary field when supported.
        experiences: Extracted experience rows.
        educations: Extracted education rows.
        skills: Extracted skill rows.
    """

    full_name: ProfileImportScalarField | None = None
    email: ProfileImportScalarField | None = None
    phone: ProfileImportScalarField | None = None
    location: ProfileImportScalarField | None = None
    headline: ProfileImportScalarField | None = None
    summary: ProfileImportScalarField | None = None
    experiences: list[ProfileImportExperienceItem] = Field(default_factory=list)
    educations: list[ProfileImportEducationItem] = Field(default_factory=list)
    skills: list[ProfileImportSkillItem] = Field(default_factory=list)


class ProfileImportAuditScalarSuggestion(StrictContractModel):
    """One supervisor suggestion for scalar field placement.

    Attributes:
        field_name: Source scalar field name.
        action: Suggested action for the scalar value.
        suggested_value: Optional replacement/moved value.
        reason: Optional short reason for review logging.
    """

    field_name: Literal["full_name", "email", "phone", "location", "headline", "summary"]
    action: Literal[
        "keep",
        "drop",
        "replace",
        "move_to_location",
        "move_to_headline",
        "move_to_summary",
        "move_to_education",
    ]
    suggested_value: str | None = None
    reason: str | None = None


class ProfileImportAuditResponse(StrictContractModel):
    """Structured supervisor output for profile import extraction.

    Attributes:
        scalar_suggestions: Scalar correction suggestions.
        missing_signals: Important profile elements likely present but still missing.
        warnings: Additional extraction quality warnings.
    """

    scalar_suggestions: list[ProfileImportAuditScalarSuggestion] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CvRewriteResponse(StrictContractModel):
    """Structured response for CV summary and bullet rewrites.

    Attributes:
        summary: Optional rewritten summary paragraph.
        bullets: Rewritten bullet lines.
    """

    summary: str | None = None
    bullets: list[str] = Field(default_factory=list)


class FactRewriteItem(StrictContractModel):
    """Rewritten fact entry for selected tailoring facts.

    Attributes:
        fact_key: Stable selected fact key.
        rewritten_text: Rewritten content for the fact.
    """

    fact_key: str
    rewritten_text: str


class FactRewriteResponse(StrictContractModel):
    """Structured rewrite response for selected profile facts.

    Attributes:
        rewrites: Rewritten fact entries.
    """

    rewrites: list[FactRewriteItem] = Field(default_factory=list)


class CoverLetterResponse(StrictContractModel):
    """Structured cover letter generation response.

    Attributes:
        cover_letter: Generated cover letter body text.
    """

    cover_letter: str


class ValidationIssue(StrictContractModel):
    """Validation issue detected by model-assisted checks.

    Attributes:
        issue_type: Short machine-readable issue label.
        message: Human-readable issue description.
        severity: Relative severity level.
        fact_key: Optional source fact key when available.
    """

    issue_type: str
    message: str
    severity: Literal["low", "medium", "high"] = "medium"
    fact_key: str | None = None


class ValidationResponse(StrictContractModel):
    """Structured validation result for generated content.

    Attributes:
        is_valid: True when no blocking issues were found.
        issues: Validation issue list.
    """

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
