"""API schemas for profile import ingestion and review workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.profile import MasterProfileResponse


class ProfileImportSourceResponse(BaseModel):
    """Response payload for one import source."""

    id: str
    source_type: str
    source_label: str
    file_name: str | None
    source_url: str | None
    created_at: datetime


class ProfileImportDecisionResponse(BaseModel):
    """Response payload for one field review decision entry."""

    id: str
    decision: str
    final_value: str | None
    reviewer_note: str | None
    created_at: datetime


class ProfileImportFieldResponse(BaseModel):
    """Response payload for one extracted review field."""

    id: str
    field_path: str
    section_type: str
    source_locator: str | None
    source_excerpt: str | None
    extracted_value: str | None
    suggested_value: str | None
    confidence_score: int
    decision_status: str
    recommended_decision: str
    review_risk: str
    sort_order: int
    decisions: list[ProfileImportDecisionResponse]


class ProfileImportConflictResponse(BaseModel):
    """Response payload for one import conflict row."""

    id: str
    field_path: str
    conflict_type: str
    existing_value: str | None
    imported_value: str | None
    resolution_status: str
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class ProfileImportAppliedFactResponse(BaseModel):
    """Response payload for one applied-fact traceability mapping."""

    id: str
    field_id: str | None
    target_entity_type: str
    target_entity_id: str | None
    target_field_path: str
    applied_value: str | None
    created_at: datetime


class ProfileImportRunResponse(BaseModel):
    """Response payload for one profile import run."""

    id: str
    source: ProfileImportSourceResponse
    extractor_name: str
    extractor_version: str | None
    status: str
    detected_language: str | None
    created_at: datetime
    updated_at: datetime
    fields: list[ProfileImportFieldResponse]
    conflicts: list[ProfileImportConflictResponse]
    applied_facts: list[ProfileImportAppliedFactResponse]


class ProfileImportRunListResponse(BaseModel):
    """Response payload for listing profile import runs."""

    runs: list[ProfileImportRunResponse]


class WebsiteImportRequest(BaseModel):
    """Request payload for portfolio website import."""

    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=3, ge=1, le=10)


class FieldDecisionInput(BaseModel):
    """Request payload for one field review decision."""

    field_id: str
    decision: Literal["approve", "reject", "edit"]
    edited_value: str | None = None
    reviewer_note: str | None = None


class ConflictResolutionInput(BaseModel):
    """Request payload for one conflict resolution."""

    conflict_id: str
    resolution_status: Literal["pending", "keep_existing", "accept_import", "manual", "rejected"]
    resolution_note: str | None = None


class ProfileImportReviewRequest(BaseModel):
    """Request payload for import review updates."""

    decisions: list[FieldDecisionInput] = Field(default_factory=list)
    conflict_resolutions: list[ConflictResolutionInput] = Field(default_factory=list)


class ProfileImportRejectRequest(BaseModel):
    """Request payload to reject a profile import run."""

    note: str | None = None


class ProfileImportApplyResponse(BaseModel):
    """Response payload for applying reviewed import data to profile."""

    run: ProfileImportRunResponse
    profile: MasterProfileResponse
