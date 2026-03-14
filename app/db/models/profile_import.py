"""ORM models for profile import ingestion, review, and traceability."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Returns:
        Timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class ProfileImportSourceModel(Base):
    """Source metadata for one import attempt.

    Attributes:
        id: Primary identifier.
        source_type: Source type such as ``cv_document`` or ``portfolio_website``.
        source_label: Human-readable source label.
        file_name: Uploaded file name for CV imports.
        file_path: Stored file path for uploaded source.
        source_url: Source URL for website imports.
        checksum_sha256: Optional checksum for uploaded files.
        created_at: Source creation timestamp.
        runs: Import runs associated with this source.
    """

    __tablename__ = "profile_import_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    runs: Mapped[list[ProfileImportRunModel]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="ProfileImportRunModel.created_at.desc()",
    )


class ProfileImportRunModel(Base):
    """One extraction/classification run for a source.

    Attributes:
        id: Primary identifier.
        source_id: Parent import source identifier.
        extractor_name: Parser/extractor implementation name.
        extractor_version: Optional parser/extractor version.
        status: Run state (extracted/reviewed/applied/rejected/failed).
        detected_language: Optional detected language code.
        raw_text: Normalized extracted text.
        structured_payload_json: JSON string with structured extraction draft.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        source: Parent source relationship.
        fields: Extracted import fields for review.
        conflicts: Conflict rows for review.
        applied_facts: Traceability rows for applied fields.
    """

    __tablename__ = "profile_import_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profile_import_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    extractor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="extracted")
    detected_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    source: Mapped[ProfileImportSourceModel] = relationship(back_populates="runs")
    fields: Mapped[list[ProfileImportFieldModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ProfileImportFieldModel.sort_order",
    )
    conflicts: Mapped[list[ProfileImportConflictModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ProfileImportConflictModel.created_at",
    )
    applied_facts: Mapped[list[ProfileImportAppliedFactModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ProfileImportAppliedFactModel.created_at",
    )


class ProfileImportFieldModel(Base):
    """One extracted field candidate row for review workflow."""

    __tablename__ = "profile_import_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    import_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profile_import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    section_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    run: Mapped[ProfileImportRunModel] = relationship(back_populates="fields")
    decisions: Mapped[list[ProfileImportDecisionModel]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
        order_by="ProfileImportDecisionModel.created_at.desc()",
    )


class ProfileImportDecisionModel(Base):
    """Audit row for one explicit field-level review decision."""

    __tablename__ = "profile_import_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    field_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profile_import_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    final_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    field: Mapped[ProfileImportFieldModel] = relationship(back_populates="decisions")


class ProfileImportConflictModel(Base):
    """Conflict row comparing imported values with existing profile facts."""

    __tablename__ = "profile_import_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    import_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profile_import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    existing_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    run: Mapped[ProfileImportRunModel] = relationship(back_populates="conflicts")


class ProfileImportAppliedFactModel(Base):
    """Traceability mapping from imported fields to applied profile facts."""

    __tablename__ = "profile_import_applied_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    import_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profile_import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("profile_import_fields.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[ProfileImportRunModel] = relationship(back_populates="applied_facts")
