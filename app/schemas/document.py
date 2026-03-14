"""API schemas for document generation and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentGenerateRequest(BaseModel):
    """Request payload for document generation from tailored snapshots."""

    snapshot_id: str
    language: Literal["en", "de"] | None = None
    formats: list[Literal["html", "pdf", "docx"]] = Field(default_factory=lambda: ["pdf", "docx"])


class DocumentArtifactResponse(BaseModel):
    """Response payload for one generated document artifact."""

    id: str
    snapshot_id: str
    document_type: str
    language: str
    file_format: str
    mime_type: str
    file_name: str
    file_size_bytes: int
    created_at: datetime


class DocumentGenerateResponse(BaseModel):
    """Response payload after generating one logical document type."""

    snapshot_id: str
    document_type: str
    artifacts: list[DocumentArtifactResponse]


class DocumentArtifactListResponse(BaseModel):
    """Response payload listing snapshot artifacts."""

    snapshot_id: str
    artifacts: list[DocumentArtifactResponse]
