"""API schemas for profile module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ExperienceInput(BaseModel):
    """Input schema for a profile experience entry.

    Attributes:
        company: Employer name.
        title: Role title.
        start_date: Optional start date.
        end_date: Optional end date.
        description: Optional role description.
    """

    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class EducationInput(BaseModel):
    """Input schema for a profile education entry."""

    institution: str = Field(min_length=1, max_length=255)
    degree: str = Field(min_length=1, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None


class SkillInput(BaseModel):
    """Input schema for a profile skill entry."""

    skill_name: str = Field(min_length=1, max_length=255)
    level: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=128)


class MasterProfileCreateRequest(BaseModel):
    """Request schema for creating a master profile."""

    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    experiences: list[ExperienceInput] = Field(default_factory=list)
    educations: list[EducationInput] = Field(default_factory=list)
    skills: list[SkillInput] = Field(default_factory=list)


class MasterProfileUpdateRequest(BaseModel):
    """Request schema for updating a master profile via new version creation."""

    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    experiences: list[ExperienceInput] = Field(default_factory=list)
    educations: list[EducationInput] = Field(default_factory=list)
    skills: list[SkillInput] = Field(default_factory=list)


class ExperienceResponse(BaseModel):
    """Response schema for experience entry."""

    id: str
    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None
    sort_order: int


class EducationResponse(BaseModel):
    """Response schema for education entry."""

    id: str
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    sort_order: int


class SkillResponse(BaseModel):
    """Response schema for skill entry."""

    id: str
    skill_name: str
    level: str | None
    category: str | None
    sort_order: int


class MasterProfileVersionResponse(BaseModel):
    """Response schema for one profile version."""

    version_id: str
    profile_id: str
    version_number: int
    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    created_at: datetime
    experiences: list[ExperienceResponse]
    educations: list[EducationResponse]
    skills: list[SkillResponse]


class MasterProfileResponse(BaseModel):
    """Response schema for the active profile and active version."""

    profile_id: str
    created_at: datetime
    updated_at: datetime
    active_version: MasterProfileVersionResponse


class MasterProfileVersionListResponse(BaseModel):
    """Response schema for profile version listing."""

    profile_id: str
    versions: list[MasterProfileVersionResponse]


class DeleteProfileResponse(BaseModel):
    """Response schema for profile delete requests."""

    deleted: bool
