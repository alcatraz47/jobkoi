"""Repository for generated document artifact persistence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.document import DocumentArtifactModel


@dataclass(frozen=True)
class DocumentArtifactCreatePayload:
    """Payload for persisting a generated document artifact."""

    snapshot_id: str
    document_type: str
    language: str
    file_format: str
    mime_type: str
    file_name: str
    file_path: str
    file_size_bytes: int


class DocumentRepository:
    """Persistence operations for generated document artifacts."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: Active SQLAlchemy session.
        """

        self._session = session

    def create_artifact(self, payload: DocumentArtifactCreatePayload) -> DocumentArtifactModel:
        """Persist one generated document artifact.

        Args:
            payload: Artifact creation payload.

        Returns:
            Persisted artifact model.
        """

        model = DocumentArtifactModel(
            snapshot_id=payload.snapshot_id,
            document_type=payload.document_type,
            language=payload.language,
            file_format=payload.file_format,
            mime_type=payload.mime_type,
            file_name=payload.file_name,
            file_path=payload.file_path,
            file_size_bytes=payload.file_size_bytes,
        )
        self._session.add(model)
        self._session.flush()
        return model

    def get_artifact(self, artifact_id: str) -> DocumentArtifactModel | None:
        """Fetch one document artifact by identifier.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Artifact model when found.
        """

        stmt = select(DocumentArtifactModel).where(DocumentArtifactModel.id == artifact_id)
        return self._session.scalar(stmt)

    def list_by_snapshot(self, snapshot_id: str) -> list[DocumentArtifactModel]:
        """List all artifacts generated for one snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Artifact list ordered by creation time descending.
        """

        stmt = (
            select(DocumentArtifactModel)
            .where(DocumentArtifactModel.snapshot_id == snapshot_id)
            .order_by(DocumentArtifactModel.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())
