"""Repository for profile import ingestion, review, and traceability data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.profile_import import (
    ProfileImportAppliedFactModel,
    ProfileImportConflictModel,
    ProfileImportDecisionModel,
    ProfileImportFieldModel,
    ProfileImportRunModel,
    ProfileImportSourceModel,
)


@dataclass(frozen=True)
class ImportSourcePayload:
    """Input payload for one profile import source."""

    source_type: str
    source_label: str
    file_name: str | None
    file_path: str | None
    source_url: str | None
    checksum_sha256: str | None


@dataclass(frozen=True)
class ImportFieldPayload:
    """Input payload for one extracted import field row."""

    field_path: str
    section_type: str
    source_locator: str | None
    source_excerpt: str | None
    extracted_value: str
    suggested_value: str
    confidence_score: int
    decision_status: str
    sort_order: int


@dataclass(frozen=True)
class ImportConflictPayload:
    """Input payload for one import conflict row."""

    field_path: str
    conflict_type: str
    existing_value: str | None
    imported_value: str | None


@dataclass(frozen=True)
class ImportRunPayload:
    """Input payload for one profile import run."""

    extractor_name: str
    extractor_version: str | None
    status: str
    detected_language: str | None
    raw_text: str
    structured_payload_json: str
    fields: list[ImportFieldPayload]
    conflicts: list[ImportConflictPayload]


@dataclass(frozen=True)
class FieldDecisionPayload:
    """Input payload for one review decision on an import field."""

    field_id: str
    decision: str
    final_value: str | None
    reviewer_note: str | None


@dataclass(frozen=True)
class ConflictResolutionPayload:
    """Input payload for one conflict resolution."""

    conflict_id: str
    resolution_status: str
    resolution_note: str | None


@dataclass(frozen=True)
class AppliedFactPayload:
    """Input payload for one applied-fact traceability row."""

    field_id: str | None
    target_entity_type: str
    target_entity_id: str | None
    target_field_path: str
    applied_value: str | None


class ProfileImportRepository:
    """Persistence operations for profile import workflow entities."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with active SQLAlchemy session.

        Args:
            session: Active database session.
        """

        self._session = session

    def create_source(self, payload: ImportSourcePayload) -> ProfileImportSourceModel:
        """Create and persist one import source row.

        Args:
            payload: Source input payload.

        Returns:
            Persisted source row.
        """

        source = ProfileImportSourceModel(
            source_type=payload.source_type,
            source_label=payload.source_label,
            file_name=payload.file_name,
            file_path=payload.file_path,
            source_url=payload.source_url,
            checksum_sha256=payload.checksum_sha256,
        )
        self._session.add(source)
        self._session.flush()
        return source

    def create_run(self, source_id: str, payload: ImportRunPayload) -> ProfileImportRunModel:
        """Create and persist one import run with extracted fields/conflicts.

        Args:
            source_id: Parent source identifier.
            payload: Run creation payload.

        Returns:
            Persisted run row.
        """

        run = ProfileImportRunModel(
            source_id=source_id,
            extractor_name=payload.extractor_name,
            extractor_version=payload.extractor_version,
            status=payload.status,
            detected_language=payload.detected_language,
            raw_text=payload.raw_text,
            structured_payload_json=payload.structured_payload_json,
            fields=[
                ProfileImportFieldModel(
                    field_path=item.field_path,
                    section_type=item.section_type,
                    source_locator=item.source_locator,
                    source_excerpt=item.source_excerpt,
                    extracted_value=item.extracted_value,
                    suggested_value=item.suggested_value,
                    confidence_score=item.confidence_score,
                    decision_status=item.decision_status,
                    sort_order=item.sort_order,
                )
                for item in payload.fields
            ],
            conflicts=[
                ProfileImportConflictModel(
                    field_path=item.field_path,
                    conflict_type=item.conflict_type,
                    existing_value=item.existing_value,
                    imported_value=item.imported_value,
                )
                for item in payload.conflicts
            ],
        )
        self._session.add(run)
        self._session.flush()
        return run

    def get_run(self, run_id: str) -> ProfileImportRunModel | None:
        """Fetch one import run with source, fields, decisions, and conflicts.

        Args:
            run_id: Import run identifier.

        Returns:
            Loaded run row or ``None``.
        """

        stmt = (
            select(ProfileImportRunModel)
            .where(ProfileImportRunModel.id == run_id)
            .options(
                selectinload(ProfileImportRunModel.source),
                selectinload(ProfileImportRunModel.fields).selectinload(ProfileImportFieldModel.decisions),
                selectinload(ProfileImportRunModel.conflicts),
                selectinload(ProfileImportRunModel.applied_facts),
            )
        )
        return self._session.scalar(stmt)

    def list_runs(self, *, limit: int = 50) -> list[ProfileImportRunModel]:
        """List import runs ordered by creation timestamp descending.

        Args:
            limit: Maximum run rows.

        Returns:
            Ordered import run list.
        """

        stmt = (
            select(ProfileImportRunModel)
            .order_by(ProfileImportRunModel.created_at.desc())
            .limit(limit)
            .options(selectinload(ProfileImportRunModel.source))
        )
        return list(self._session.scalars(stmt).all())

    def update_field_decisions(
        self,
        *,
        run: ProfileImportRunModel,
        decisions: list[FieldDecisionPayload],
    ) -> None:
        """Apply field-level decision updates and append decision audit rows.

        Args:
            run: Target import run.
            decisions: Field decision payload list.
        """

        fields_by_id = {field.id: field for field in run.fields}
        for item in decisions:
            field = fields_by_id.get(item.field_id)
            if field is None:
                continue

            field.decision_status = _decision_to_status(item.decision)
            if item.final_value is not None:
                field.suggested_value = item.final_value

            self._session.add(
                ProfileImportDecisionModel(
                    field_id=field.id,
                    decision=item.decision,
                    final_value=item.final_value,
                    reviewer_note=item.reviewer_note,
                )
            )

        self._session.flush()

    def update_conflict_resolutions(
        self,
        *,
        run: ProfileImportRunModel,
        resolutions: list[ConflictResolutionPayload],
    ) -> None:
        """Apply resolution statuses to conflict rows.

        Args:
            run: Target import run.
            resolutions: Conflict resolution payload list.
        """

        conflicts_by_id = {row.id: row for row in run.conflicts}
        for item in resolutions:
            conflict = conflicts_by_id.get(item.conflict_id)
            if conflict is None:
                continue

            conflict.resolution_status = item.resolution_status
            conflict.resolution_note = item.resolution_note

        self._session.flush()

    def set_run_status(self, run: ProfileImportRunModel, status: str) -> None:
        """Update import run status.

        Args:
            run: Target run row.
            status: New run status.
        """

        run.status = status
        self._session.add(run)
        self._session.flush()

    def add_applied_facts(self, *, run_id: str, rows: list[AppliedFactPayload]) -> None:
        """Persist applied-fact traceability rows.

        Args:
            run_id: Parent import run identifier.
            rows: Applied fact payload list.
        """

        for row in rows:
            self._session.add(
                ProfileImportAppliedFactModel(
                    import_run_id=run_id,
                    field_id=row.field_id,
                    target_entity_type=row.target_entity_type,
                    target_entity_id=row.target_entity_id,
                    target_field_path=row.target_field_path,
                    applied_value=row.applied_value,
                )
            )

        self._session.flush()


    def count_runs_for_source(self, source_id: str) -> int:
        """Count import runs for one source identifier.

        Args:
            source_id: Import source identifier.

        Returns:
            Number of import runs for the source.
        """

        stmt = select(func.count(ProfileImportRunModel.id)).where(ProfileImportRunModel.source_id == source_id)
        count = self._session.scalar(stmt)
        return int(count or 0)

    def delete_run(self, run: ProfileImportRunModel) -> None:
        """Delete one import run row and cascading children.

        Args:
            run: Import run model instance.
        """

        self._session.delete(run)
        self._session.flush()

    def delete_source_by_id(self, source_id: str) -> None:
        """Delete one import source row by identifier when present.

        Args:
            source_id: Import source identifier.
        """

        source = self._session.get(ProfileImportSourceModel, source_id)
        if source is None:
            return

        self._session.delete(source)
        self._session.flush()


def _decision_to_status(decision: str) -> str:
    """Map review decisions to field decision status values."""

    if decision == "approve":
        return "approved"
    if decision == "reject":
        return "rejected"
    if decision == "edit":
        return "edited"
    return "pending"
