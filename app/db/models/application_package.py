"""ORM models for reproducible application package persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return current UTC timestamp.

    Returns:
        Current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class ApplicationPackageModel(Base):
    """Stored reproducible application package.

    Attributes:
        id: Package identifier.
        job_post_id: Linked job post identifier.
        job_analysis_id: Linked job analysis identifier.
        tailoring_plan_id: Linked tailoring plan identifier.
        profile_snapshot_id: Linked immutable tailored snapshot identifier.
        language: Package language code.
        status: Package lifecycle status.
        created_at: Creation timestamp.
        documents: Linked document artifact entries.
        events: Package audit events.
    """

    __tablename__ = "application_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_posts.id", ondelete="RESTRICT"), nullable=False
    )
    job_analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_analyses.id", ondelete="RESTRICT"), nullable=False
    )
    tailoring_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tailoring_plans.id", ondelete="RESTRICT"), nullable=False
    )
    profile_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profile_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    documents: Mapped[list[ApplicationPackageDocumentModel]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="ApplicationPackageDocumentModel.created_at",
    )
    events: Mapped[list[ApplicationPackageEventModel]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="ApplicationPackageEventModel.created_at",
    )


class ApplicationPackageDocumentModel(Base):
    """Linked document artifact snapshot for a package."""

    __tablename__ = "application_package_documents"
    __table_args__ = (
        UniqueConstraint("application_package_id", "artifact_id", name="uq_package_artifact"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("application_packages.id", ondelete="CASCADE"), nullable=False
    )
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    package: Mapped[ApplicationPackageModel] = relationship(back_populates="documents")


class ApplicationPackageEventModel(Base):
    """Audit event emitted during package creation or updates."""

    __tablename__ = "application_package_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("application_packages.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    package: Mapped[ApplicationPackageModel] = relationship(back_populates="events")
