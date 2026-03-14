"""ORM model for generated document artifact persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return current UTC timestamp.

    Returns:
        Current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class DocumentArtifactModel(Base):
    """Generated document artifact linked to a tailored snapshot.

    Attributes:
        id: Artifact identifier.
        snapshot_id: Source tailored snapshot identifier.
        document_type: Logical document type, for example ``cv``.
        language: Language code.
        file_format: File format, for example ``pdf``.
        mime_type: MIME type for download responses.
        file_name: Generated file name.
        file_path: Absolute file path on local storage.
        file_size_bytes: Stored file size in bytes.
        created_at: Creation timestamp.
    """

    __tablename__ = "document_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profile_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    snapshot = relationship("ProfileSnapshotModel")
