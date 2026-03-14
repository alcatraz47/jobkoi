"""Repository for application package persistence and retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.application_package import (
    ApplicationPackageDocumentModel,
    ApplicationPackageEventModel,
    ApplicationPackageModel,
)


@dataclass(frozen=True)
class ApplicationPackageDocumentPayload:
    """Payload for linking one document artifact to a package."""

    artifact_id: str
    document_type: str
    language: str
    file_format: str
    file_name: str
    file_path: str
    file_size_bytes: int
    checksum_sha256: str | None


@dataclass(frozen=True)
class ApplicationPackageEventPayload:
    """Payload for creating one package audit event."""

    event_type: str
    message: str


@dataclass(frozen=True)
class ApplicationPackageCreatePayload:
    """Payload for creating a reproducible application package."""

    job_post_id: str
    job_analysis_id: str
    tailoring_plan_id: str
    profile_snapshot_id: str
    language: str
    status: str
    documents: list[ApplicationPackageDocumentPayload]
    events: list[ApplicationPackageEventPayload]


class ApplicationPackageRepository:
    """Persistence operations for application packages."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: Active SQLAlchemy session.
        """

        self._session = session

    def create_package(self, payload: ApplicationPackageCreatePayload) -> ApplicationPackageModel:
        """Persist one application package with links and audit events.

        Args:
            payload: Package creation payload.

        Returns:
            Persisted package model.
        """

        package = ApplicationPackageModel(
            job_post_id=payload.job_post_id,
            job_analysis_id=payload.job_analysis_id,
            tailoring_plan_id=payload.tailoring_plan_id,
            profile_snapshot_id=payload.profile_snapshot_id,
            language=payload.language,
            status=payload.status,
            documents=[
                ApplicationPackageDocumentModel(
                    artifact_id=item.artifact_id,
                    document_type=item.document_type,
                    language=item.language,
                    file_format=item.file_format,
                    file_name=item.file_name,
                    file_path=item.file_path,
                    file_size_bytes=item.file_size_bytes,
                    checksum_sha256=item.checksum_sha256,
                )
                for item in payload.documents
            ],
            events=[
                ApplicationPackageEventModel(
                    event_type=item.event_type,
                    message=item.message,
                )
                for item in payload.events
            ],
        )
        self._session.add(package)
        self._session.flush()
        return package

    def get_package(self, package_id: str) -> ApplicationPackageModel | None:
        """Fetch one application package by identifier.

        Args:
            package_id: Package identifier.

        Returns:
            Package model with linked docs/events when found.
        """

        stmt = (
            select(ApplicationPackageModel)
            .where(ApplicationPackageModel.id == package_id)
            .options(
                selectinload(ApplicationPackageModel.documents),
                selectinload(ApplicationPackageModel.events),
            )
        )
        return self._session.scalar(stmt)

    def list_packages(self) -> list[ApplicationPackageModel]:
        """List application packages ordered by newest first.

        Returns:
            Package list with linked docs/events.
        """

        stmt = (
            select(ApplicationPackageModel)
            .order_by(ApplicationPackageModel.created_at.desc())
            .options(
                selectinload(ApplicationPackageModel.documents),
                selectinload(ApplicationPackageModel.events),
            )
        )
        return list(self._session.scalars(stmt).all())
