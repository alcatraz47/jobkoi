"""API schemas for job ingestion and analysis."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class JobPostCreateRequest(BaseModel):
    """Request payload for job post submission.

    Attributes:
        title: Job title.
        description: Raw pasted job description.
        company: Optional company name.
    """

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    company: str | None = Field(default=None, max_length=255)


class JobPostResponse(BaseModel):
    """Response payload for stored job post."""

    id: str
    title: str
    company: str | None
    description_raw: str
    normalized_description: str
    detected_language: str
    created_at: datetime
    updated_at: datetime


class JobAnalysisCreateRequest(BaseModel):
    """Request payload for job analysis generation.

    Attributes:
        use_llm: Enables optional adapter-based LLM extraction.
    """

    use_llm: bool = False


class JobRequirementResponse(BaseModel):
    """Response payload for one extracted requirement."""

    id: str
    text: str
    requirement_type: str
    is_must_have: bool
    is_nice_to_have: bool
    priority_score: int
    source: str


class JobAnalysisResponse(BaseModel):
    """Response payload for structured job analysis."""

    id: str
    job_post_id: str
    normalized_title: str
    detected_language: str
    summary: str
    created_at: datetime
    requirements: list[JobRequirementResponse]
