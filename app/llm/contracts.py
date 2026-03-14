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
