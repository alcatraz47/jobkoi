"""API schemas for tailoring plans and profile snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TailoringPlanCreateRequest(BaseModel):
    """Request payload for deterministic tailoring plan creation."""

    job_analysis_id: str
    profile_version_id: str | None = None
    target_language: Literal["en", "de"] = "en"
    max_experiences: int = Field(default=4, ge=1, le=20)
    max_skills: int = Field(default=10, ge=1, le=40)
    max_educations: int = Field(default=2, ge=0, le=10)


class TailoringPlanFactResponse(BaseModel):
    """Response payload for one scored tailoring fact."""

    fact_key: str
    fact_type: str
    source_entity_id: str | None
    text: str
    relevance_score: int
    is_selected: bool
    selection_reason: str


class TailoringPlanResponse(BaseModel):
    """Response payload for a tailoring plan."""

    id: str
    job_analysis_id: str
    profile_version_id: str
    target_language: str
    summary: str
    created_at: datetime
    selected_item_count: int
    items: list[TailoringPlanFactResponse]


class SnapshotRewriteInput(BaseModel):
    """Manual rewrite input for one selected fact."""

    fact_key: str
    rewritten_text: str = Field(min_length=1)


class TailoredSnapshotCreateRequest(BaseModel):
    """Request payload for creating a tailored snapshot."""

    tailoring_plan_id: str
    rewrites: list[SnapshotRewriteInput] = Field(default_factory=list)
    use_llm_rewrite: bool = False


class SnapshotExperienceResponse(BaseModel):
    """Response payload for snapshot experience entry."""

    id: str
    source_experience_id: str | None
    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None
    relevance_score: int
    sort_order: int


class SnapshotEducationResponse(BaseModel):
    """Response payload for snapshot education entry."""

    id: str
    source_education_id: str | None
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    relevance_score: int
    sort_order: int


class SnapshotSkillResponse(BaseModel):
    """Response payload for snapshot skill entry."""

    id: str
    source_skill_id: str | None
    skill_name: str
    level: str | None
    category: str | None
    relevance_score: int
    sort_order: int


class TailoredSnapshotResponse(BaseModel):
    """Response payload for tailored snapshot."""

    id: str
    tailoring_plan_id: str
    profile_version_id: str
    target_language: str
    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    created_at: datetime
    experiences: list[SnapshotExperienceResponse]
    educations: list[SnapshotEducationResponse]
    skills: list[SnapshotSkillResponse]
