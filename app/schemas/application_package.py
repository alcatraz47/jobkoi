"""API schemas for reproducible application package operations."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApplicationPackageCreateRequest(BaseModel):
    """Request payload for creating a reproducible application package."""

    job_post_id: str
    job_analysis_id: str
    tailoring_plan_id: str
    profile_snapshot_id: str
    document_artifact_ids: list[str] = Field(default_factory=list)


class ApplicationPackageDocumentResponse(BaseModel):
    """Response payload for one linked package document artifact."""

    id: str
    artifact_id: str
    document_type: str
    language: str
    file_format: str
    file_name: str
    file_size_bytes: int
    checksum_sha256: str | None
    created_at: datetime


class ApplicationPackageEventResponse(BaseModel):
    """Response payload for one package audit event."""

    id: str
    event_type: str
    message: str
    created_at: datetime


class ApplicationPackageResponse(BaseModel):
    """Response payload for one application package."""

    id: str
    job_post_id: str
    job_analysis_id: str
    tailoring_plan_id: str
    profile_snapshot_id: str
    language: str
    status: str
    created_at: datetime
    documents: list[ApplicationPackageDocumentResponse]
    events: list[ApplicationPackageEventResponse]


class ApplicationPackageListResponse(BaseModel):
    """Response payload for listing stored application packages."""

    packages: list[ApplicationPackageResponse]
