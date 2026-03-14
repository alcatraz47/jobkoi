"""Service for CV and portfolio website profile import workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.profile_import import ProfileImportRunModel
from app.db.repositories.profile_import_repository import (
    AppliedFactPayload,
    ConflictResolutionPayload,
    FieldDecisionPayload,
    ImportConflictPayload,
    ImportFieldPayload,
    ImportRunPayload,
    ImportSourcePayload,
    ProfileImportRepository,
)
from app.domain.profile_import_builders import (
    build_imported_profile_from_text,
    detect_import_language,
    flatten_imported_profile_to_fields,
)
from app.domain.profile_import_confidence import (
    ImportReviewPolicy,
    default_decision_status,
    recommend_review_decision,
    risk_level_for_field,
)
from app.domain.profile_import_conflicts import detect_import_conflicts
from app.domain.job_text import normalize_text
from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)
from app.schemas.profile import (
    EducationInput,
    ExperienceInput,
    MasterProfileCreateRequest,
    MasterProfileResponse,
    MasterProfileUpdateRequest,
    SkillInput,
)
from app.schemas.profile_import import (
    ConflictResolutionInput,
    FieldDecisionInput,
    ProfileImportApplyResponse,
    ProfileImportAppliedFactResponse,
    ProfileImportConflictResponse,
    ProfileImportDecisionResponse,
    ProfileImportDeleteResponse,
    ProfileImportFieldResponse,
    ProfileImportRejectRequest,
    ProfileImportReviewRequest,
    ProfileImportRunListResponse,
    ProfileImportRunResponse,
    ProfileImportSourceResponse,
    WebsiteImportRequest,
)
from app.services.profile_import_extractors import (
    CvImportExtractor,
    ProfileImportExtractionError,
    WebsiteImportExtractor,
    compute_sha256_bytes,
)
from app.llm import ProfileImportExtractionHelper, get_ollama_client
from app.llm.contracts import ProfileImportExtractionResponse, ProfileImportScalarField
from app.llm.errors import LlmError
from app.services.profile_service import ProfileNotFoundError, ProfileService


_INDEXED_PATH_PATTERN = re.compile(r"^(?P<section>[a-z_]+)\[(?P<index>\d+)]\.(?P<field>[a-z_]+)$")


class ProfileImportRunNotFoundError(Exception):
    """Raised when a requested profile import run does not exist."""


class ProfileImportValidationError(Exception):
    """Raised when import review or apply validation fails."""


class ProfileImportService:
    """Service coordinating profile import ingestion, review, and apply flow."""

    def __init__(
        self,
        session: Session,
        *,
        cv_extractor: CvImportExtractor | None = None,
        website_extractor: WebsiteImportExtractor | None = None,
        import_storage_dir: Path | None = None,
    ) -> None:
        """Initialize profile import service.

        Args:
            session: Active database session.
            cv_extractor: Optional CV extraction adapter.
            website_extractor: Optional website extraction adapter.
            import_storage_dir: Optional local storage directory for source files.
        """

        self._session = session
        self._repository = ProfileImportRepository(session)
        self._profile_service = ProfileService(session)
        settings = get_settings()

        self._cv_extractor = cv_extractor or CvImportExtractor()
        self._website_extractor = website_extractor or WebsiteImportExtractor()
        if import_storage_dir is None:
            import_storage_dir = Path(
                getattr(settings, "import_storage_dir", "storage/imports")
            )
        self._import_storage_dir = import_storage_dir
        self._review_policy = ImportReviewPolicy(
            auto_approve_min_confidence=int(
                getattr(settings, "profile_import_auto_approve_min_confidence", 94)
            )
        )
        self._auto_approve_enabled = bool(
            getattr(settings, "profile_import_auto_approve_enabled", True)
        )
        self._profile_import_llm_enabled = bool(
            getattr(settings, "profile_import_llm_enabled", False)
        )
        self._profile_import_llm_max_input_chars = int(
            getattr(settings, "profile_import_llm_max_input_chars", 24000)
        )
        self._profile_import_extraction_helper: ProfileImportExtractionHelper | None = None
        if self._profile_import_llm_enabled:
            self._profile_import_extraction_helper = self._build_default_profile_import_extraction_helper()

    def import_cv(
        self,
        *,
        file_name: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> ProfileImportRunResponse:
        """Create a CV-based import run from uploaded file bytes.

        Args:
            file_name: Original uploaded file name.
            content_type: Uploaded content type.
            file_bytes: Uploaded file bytes.

        Returns:
            Created import run response.

        Raises:
            ProfileImportValidationError: If file extension is unsupported.
            ProfileImportExtractionError: If source text extraction fails.
        """

        self._validate_cv_file_name(file_name)
        source_path = self._persist_source_file(file_name=file_name, file_bytes=file_bytes)
        checksum = compute_sha256_bytes(file_bytes)

        source = self._repository.create_source(
            ImportSourcePayload(
                source_type="cv_document",
                source_label=file_name,
                file_name=file_name,
                file_path=str(source_path),
                source_url=None,
                checksum_sha256=checksum,
            )
        )

        extracted = self._cv_extractor.extract_from_file(
            file_path=source_path,
            file_name=file_name,
            content_type=content_type,
        )

        run_payload = self._build_run_payload_from_text(
            raw_text=extracted.text,
            extractor_name=extracted.extractor_name,
            extractor_version=extracted.extractor_version,
            source_locator=file_name,
            source_type="cv_document",
            source_label=file_name,
        )
        run = self._repository.create_run(source.id, run_payload)
        self._session.commit()
        return self._to_run_response(run)

    def import_website(self, request: WebsiteImportRequest) -> ProfileImportRunResponse:
        """Create a website-based import run from public URL extraction.

        Args:
            request: Website import request payload.

        Returns:
            Created import run response.

        Raises:
            ProfileImportExtractionError: If website content cannot be extracted.
        """

        source = self._repository.create_source(
            ImportSourcePayload(
                source_type="portfolio_website",
                source_label=request.url,
                file_name=None,
                file_path=None,
                source_url=request.url,
                checksum_sha256=None,
            )
        )

        extractor_name, pages = self._website_extractor.extract_from_url(
            url=request.url,
            max_pages=request.max_pages,
        )

        merged = ImportedProfileDraft()
        combined_text_parts: list[str] = []
        for page in pages:
            page_draft = build_imported_profile_from_text(
                text=page.text,
                source_locator=page.url,
            )
            merged = _merge_imported_profile_drafts(base=merged, incoming=page_draft)
            combined_text_parts.append(page.text)

        merged_text = "\n".join(combined_text_parts)
        run_payload = self._build_run_payload_from_draft(
            draft=merged,
            raw_text=merged_text,
            extractor_name=extractor_name,
            extractor_version=None,
        )
        run = self._repository.create_run(source.id, run_payload)
        self._session.commit()
        return self._to_run_response(run)

    def list_runs(self) -> ProfileImportRunListResponse:
        """List profile import runs.

        Returns:
            Import run list response.
        """

        runs = [self._to_run_response(item) for item in self._repository.list_runs(limit=100)]
        return ProfileImportRunListResponse(runs=runs)

    def get_run(self, run_id: str) -> ProfileImportRunResponse:
        """Fetch one profile import run.

        Args:
            run_id: Import run identifier.

        Returns:
            Import run response.

        Raises:
            ProfileImportRunNotFoundError: If run does not exist.
        """

        run = self._require_run(run_id)
        return self._to_run_response(run)

    def review_run(self, run_id: str, request: ProfileImportReviewRequest) -> ProfileImportRunResponse:
        """Apply review decisions and conflict resolutions for one import run.

        Args:
            run_id: Import run identifier.
            request: Review update payload.

        Returns:
            Updated import run response.

        Raises:
            ProfileImportRunNotFoundError: If run does not exist.
            ProfileImportValidationError: If decision payload is invalid.
        """

        run = self._require_run(run_id)

        decision_payloads = [self._to_decision_payload(item) for item in request.decisions]
        resolution_payloads = [self._to_resolution_payload(item) for item in request.conflict_resolutions]

        self._repository.update_field_decisions(run=run, decisions=decision_payloads)
        self._repository.update_conflict_resolutions(run=run, resolutions=resolution_payloads)

        if request.decisions or request.conflict_resolutions:
            self._repository.set_run_status(run, "reviewed")

        self._session.commit()
        return self.get_run(run_id)

    def reject_run(self, run_id: str, request: ProfileImportRejectRequest) -> ProfileImportRunResponse:
        """Reject an import run without applying any extracted fields.

        Args:
            run_id: Import run identifier.
            request: Reject payload.

        Returns:
            Updated import run response.

        Raises:
            ProfileImportRunNotFoundError: If run does not exist.
        """

        _ = request
        run = self._require_run(run_id)
        self._repository.set_run_status(run, "rejected")
        self._session.commit()
        return self.get_run(run_id)

    def delete_run(self, run_id: str) -> ProfileImportDeleteResponse:
        """Delete one profile import run and attached source artifacts.

        Args:
            run_id: Import run identifier.

        Returns:
            Delete response payload.

        Raises:
            ProfileImportRunNotFoundError: If run does not exist.
        """

        run = self._require_run(run_id)
        source_id = run.source.id
        source_file_path = run.source.file_path

        self._repository.delete_run(run)
        if self._repository.count_runs_for_source(source_id) == 0:
            self._repository.delete_source_by_id(source_id)

        self._session.commit()
        _delete_source_file(source_file_path)
        return ProfileImportDeleteResponse(deleted=True, run_id=run_id)

    def apply_run(self, run_id: str) -> ProfileImportApplyResponse:
        """Apply approved/edited import fields into master profile via new version.

        Args:
            run_id: Import run identifier.

        Returns:
            Apply response with updated run and profile.

        Raises:
            ProfileImportRunNotFoundError: If run does not exist.
            ProfileImportValidationError: If unresolved conflicts or required fields are missing.
        """

        run = self._require_run(run_id)
        if run.status in {"rejected", "failed"}:
            raise ProfileImportValidationError("Rejected or failed import runs cannot be applied.")

        self._ensure_conflicts_are_resolved(run)

        selected_fields = [
            field
            for field in run.fields
            if field.decision_status in {"approved", "edited"}
            and field.suggested_value
        ]
        if not selected_fields:
            raise ProfileImportValidationError("No approved fields are available to apply.")

        existing_profile = self._try_get_profile_payload()
        payload = _build_profile_apply_payload(existing_profile)
        applied_field_paths: list[tuple[str, str]] = []

        try:
            _apply_scalar_fields(payload=payload, fields=selected_fields, applied_field_paths=applied_field_paths)
            _apply_experience_fields(
                payload=payload,
                fields=selected_fields,
                applied_field_paths=applied_field_paths,
            )
            _apply_education_fields(
                payload=payload,
                fields=selected_fields,
                applied_field_paths=applied_field_paths,
            )
            _apply_skill_fields(payload=payload, fields=selected_fields, applied_field_paths=applied_field_paths)
        except ValidationError as exc:
            raise ProfileImportValidationError(_format_validation_error(exc)) from exc

        if not payload["full_name"] or not payload["email"]:
            raise ProfileImportValidationError(
                "Applying import requires full_name and email after review decisions."
            )

        try:
            profile_response = self._save_profile_payload(existing_profile, payload)
        except ValidationError as exc:
            raise ProfileImportValidationError(_format_validation_error(exc)) from exc

        trace_rows = [
            AppliedFactPayload(
                field_id=field.id,
                target_entity_type="profile_version",
                target_entity_id=profile_response.active_version.version_id,
                target_field_path=field_path,
                applied_value=applied_value,
            )
            for field_path, applied_value in applied_field_paths
            for field in selected_fields
            if field.field_path == field_path and field.suggested_value == applied_value
        ]

        self._repository.add_applied_facts(run_id=run.id, rows=trace_rows)
        self._repository.set_run_status(run, "applied")
        self._session.commit()
        self._session.expire_all()

        return ProfileImportApplyResponse(
            run=self.get_run(run_id),
            profile=profile_response,
        )

    def _build_run_payload_from_text(
        self,
        *,
        raw_text: str,
        extractor_name: str,
        extractor_version: str | None,
        source_locator: str,
        source_type: str,
        source_label: str,
    ) -> ImportRunPayload:
        """Build repository run payload from raw text."""

        draft = build_imported_profile_from_text(text=raw_text, source_locator=source_locator)
        combined_extractor_name = extractor_name

        llm_draft = self._extract_llm_draft_for_source(
            raw_text=raw_text,
            source_type=source_type,
            source_label=source_label,
            source_locator=source_locator,
        )
        if llm_draft is not None:
            draft = _merge_imported_profile_drafts(base=draft, incoming=llm_draft)
            combined_extractor_name = f"{extractor_name}+llm"

        return self._build_run_payload_from_draft(
            draft=draft,
            raw_text=raw_text,
            extractor_name=combined_extractor_name,
            extractor_version=extractor_version,
        )

    def _build_default_profile_import_extraction_helper(self) -> ProfileImportExtractionHelper | None:
        """Build default LLM profile import helper when configured."""

        try:
            return ProfileImportExtractionHelper(get_ollama_client())
        except Exception:
            return None

    def _extract_llm_draft_for_source(
        self,
        *,
        raw_text: str,
        source_type: str,
        source_label: str,
        source_locator: str,
    ) -> ImportedProfileDraft | None:
        """Extract and validate one optional LLM draft from source text."""

        if source_type != "cv_document":
            return None
        if not self._profile_import_llm_enabled:
            return None
        if self._profile_import_extraction_helper is None:
            return None

        truncated_text = _truncate_for_llm_input(
            raw_text=raw_text,
            max_chars=self._profile_import_llm_max_input_chars,
        )
        if len(truncated_text) < 40:
            return None

        try:
            response = self._profile_import_extraction_helper.extract_profile(
                source_type=source_type,
                source_label=source_label,
                raw_text=truncated_text,
                detected_language=detect_import_language(raw_text),
            )
        except LlmError:
            return None

        llm_draft = _build_profile_draft_from_llm_response(
            response=response,
            source_locator=source_locator,
        )
        validated = _filter_profile_draft_by_source_support(
            draft=llm_draft,
            raw_text=raw_text,
        )
        if _is_empty_import_draft(validated):
            return None
        return validated

    def _build_run_payload_from_draft(
        self,
        *,
        draft: ImportedProfileDraft,
        raw_text: str,
        extractor_name: str,
        extractor_version: str | None,
    ) -> ImportRunPayload:
        """Build repository run payload from imported profile draft."""

        field_rows = flatten_imported_profile_to_fields(draft)
        existing_profile = self._try_get_profile_payload()
        conflicts = detect_import_conflicts(
            existing_profile_payload=existing_profile,
            imported_draft=draft,
        )

        conflict_paths = {item.field_path for item in conflicts}
        prepared_fields: list[ImportFieldPayload] = []
        for item in field_rows:
            status = "pending"
            if self._auto_approve_enabled and item.field_path not in conflict_paths:
                status = default_decision_status(
                    section_type=item.section_type,
                    field_path=item.field_path,
                    confidence_score=item.confidence_score,
                    policy=self._review_policy,
                )

            prepared_fields.append(
                ImportFieldPayload(
                    field_path=item.field_path,
                    section_type=item.section_type,
                    source_locator=item.source_locator,
                    source_excerpt=item.source_excerpt,
                    extracted_value=item.extracted_value,
                    suggested_value=item.suggested_value,
                    confidence_score=item.confidence_score,
                    decision_status=status,
                    sort_order=item.sort_order,
                )
            )

        return ImportRunPayload(
            extractor_name=extractor_name,
            extractor_version=extractor_version,
            status="extracted",
            detected_language=detect_import_language(raw_text),
            raw_text=raw_text,
            structured_payload_json=json.dumps(_draft_to_dict(draft), ensure_ascii=True),
            fields=prepared_fields,
            conflicts=[
                ImportConflictPayload(
                    field_path=item.field_path,
                    conflict_type=item.conflict_type,
                    existing_value=item.existing_value,
                    imported_value=item.imported_value,
                )
                for item in conflicts
            ],
        )

    def _require_run(self, run_id: str) -> ProfileImportRunModel:
        """Load import run or raise not-found error."""

        run = self._repository.get_run(run_id)
        if run is None:
            raise ProfileImportRunNotFoundError("Profile import run not found.")
        return run

    def _try_get_profile_payload(self) -> dict[str, object] | None:
        """Return existing profile payload when available."""

        try:
            profile = self._profile_service.get_profile()
        except ProfileNotFoundError:
            return None
        return profile.model_dump(mode="json")

    def _save_profile_payload(
        self,
        existing_profile_payload: dict[str, object] | None,
        payload: dict[str, Any],
    ) -> MasterProfileResponse:
        """Persist merged payload as create or versioned update."""

        if existing_profile_payload is None:
            request = MasterProfileCreateRequest.model_validate(payload)
            return self._profile_service.create_profile(request)

        request = MasterProfileUpdateRequest.model_validate(payload)
        return self._profile_service.update_profile(request)

    def _ensure_conflicts_are_resolved(self, run: ProfileImportRunModel) -> None:
        """Ensure no unresolved conflict rows remain before apply."""

        pending = [item for item in run.conflicts if item.resolution_status == "pending"]
        if pending:
            raise ProfileImportValidationError(
                "Resolve all detected conflicts before applying imported data."
            )

    def _validate_cv_file_name(self, file_name: str) -> None:
        """Validate uploaded CV file extension."""

        lowered = file_name.lower()
        if not (lowered.endswith(".pdf") or lowered.endswith(".docx")):
            raise ProfileImportValidationError("Only PDF and DOCX files are supported.")

    def _persist_source_file(self, *, file_name: str, file_bytes: bytes) -> Path:
        """Persist uploaded source file into import storage."""

        safe_name = _safe_file_name(file_name)
        target_dir = self._import_storage_dir / "cv"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4().hex}_{safe_name}"
        target_path.write_bytes(file_bytes)
        return target_path

    def _to_decision_payload(self, item: FieldDecisionInput) -> FieldDecisionPayload:
        """Map API decision input to repository payload."""

        if item.decision == "edit" and (item.edited_value is None or not item.edited_value.strip()):
            raise ProfileImportValidationError("Edited decisions require non-empty edited_value.")

        final_value = item.edited_value if item.decision == "edit" else None
        return FieldDecisionPayload(
            field_id=item.field_id,
            decision=item.decision,
            final_value=final_value,
            reviewer_note=item.reviewer_note,
        )


    def _to_resolution_payload(self, item: ConflictResolutionInput) -> ConflictResolutionPayload:
        """Map API conflict resolution input to repository payload."""

        return ConflictResolutionPayload(
            conflict_id=item.conflict_id,
            resolution_status=item.resolution_status,
            resolution_note=item.resolution_note,
        )


    def _to_run_response(self, run: ProfileImportRunModel) -> ProfileImportRunResponse:
        """Map ORM import run model to API response schema."""

        return ProfileImportRunResponse(
            id=run.id,
            source=ProfileImportSourceResponse(
                id=run.source.id,
                source_type=run.source.source_type,
                source_label=run.source.source_label,
                file_name=run.source.file_name,
                source_url=run.source.source_url,
                created_at=run.source.created_at,
            ),
            extractor_name=run.extractor_name,
            extractor_version=run.extractor_version,
            status=run.status,
            detected_language=run.detected_language,
            created_at=run.created_at,
            updated_at=run.updated_at,
            fields=[
                ProfileImportFieldResponse(
                    id=item.id,
                    field_path=item.field_path,
                    section_type=item.section_type,
                    source_locator=item.source_locator,
                    source_excerpt=item.source_excerpt,
                    extracted_value=item.extracted_value,
                    suggested_value=item.suggested_value,
                    confidence_score=item.confidence_score,
                    decision_status=item.decision_status,
                    recommended_decision=recommend_review_decision(
                        section_type=item.section_type,
                        field_path=item.field_path,
                        confidence_score=item.confidence_score,
                        policy=self._review_policy,
                    ),
                    review_risk=risk_level_for_field(
                        field_path=item.field_path,
                        section_type=item.section_type,
                        confidence_score=item.confidence_score,
                    ),
                    sort_order=item.sort_order,
                    decisions=[
                        ProfileImportDecisionResponse(
                            id=decision.id,
                            decision=decision.decision,
                            final_value=decision.final_value,
                            reviewer_note=decision.reviewer_note,
                            created_at=decision.created_at,
                        )
                        for decision in item.decisions
                    ],
                )
                for item in run.fields
            ],
            conflicts=[
                ProfileImportConflictResponse(
                    id=item.id,
                    field_path=item.field_path,
                    conflict_type=item.conflict_type,
                    existing_value=item.existing_value,
                    imported_value=item.imported_value,
                    resolution_status=item.resolution_status,
                    resolution_note=item.resolution_note,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in run.conflicts
            ],
            applied_facts=[
                ProfileImportAppliedFactResponse(
                    id=item.id,
                    field_id=item.field_id,
                    target_entity_type=item.target_entity_type,
                    target_entity_id=item.target_entity_id,
                    target_field_path=item.target_field_path,
                    applied_value=item.applied_value,
                    created_at=item.created_at,
                )
                for item in run.applied_facts
            ],
        )


def _safe_file_name(file_name: str) -> str:
    """Return filesystem-safe file name."""

    normalized = re.sub(r"[^a-zA-Z0-9._-]", "_", file_name)
    return normalized or "uploaded_source"


def _draft_to_dict(draft: ImportedProfileDraft) -> dict[str, Any]:
    """Convert imported profile draft into JSON-serializable mapping."""

    return {
        "full_name": draft.full_name,
        "email": draft.email,
        "phone": draft.phone,
        "location": draft.location,
        "headline": draft.headline,
        "summary": draft.summary,
        "experiences": [
            {
                "company": item.company,
                "title": item.title,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "description": item.description,
                "source_locator": item.source_locator,
            }
            for item in draft.experiences
        ],
        "educations": [
            {
                "institution": item.institution,
                "degree": item.degree,
                "field_of_study": item.field_of_study,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "source_locator": item.source_locator,
            }
            for item in draft.educations
        ],
        "skills": [
            {
                "skill_name": item.skill_name,
                "level": item.level,
                "category": item.category,
                "source_locator": item.source_locator,
            }
            for item in draft.skills
        ],
        "unmapped_candidates": [
            {
                "text": item.text,
                "section_hint": item.section_hint,
                "reason": item.reason,
                "source_locator": item.source_locator,
            }
            for item in draft.unmapped_candidates
        ],
    }


def _merge_imported_profile_drafts(
    *,
    base: ImportedProfileDraft,
    incoming: ImportedProfileDraft,
) -> ImportedProfileDraft:
    """Merge two imported profile drafts with append-only list behavior."""

    return ImportedProfileDraft(
        full_name=base.full_name or incoming.full_name,
        email=base.email or incoming.email,
        phone=base.phone or incoming.phone,
        location=base.location or incoming.location,
        headline=base.headline or incoming.headline,
        summary=base.summary or incoming.summary,
        experiences=_merge_experiences(base.experiences, incoming.experiences),
        educations=_merge_educations(base.educations, incoming.educations),
        skills=_merge_skills(base.skills, incoming.skills),
        unmapped_candidates=_merge_unmapped_candidates(
            base.unmapped_candidates,
            incoming.unmapped_candidates,
        ),
    )


def _merge_experiences(
    base: list[Any],
    incoming: list[Any],
) -> list[Any]:
    """Merge imported experience entries by company/title key."""

    merged = list(base)
    existing_keys = {(item.company.lower(), item.title.lower()) for item in merged}
    for item in incoming:
        key = (item.company.lower(), item.title.lower())
        if key in existing_keys:
            continue
        existing_keys.add(key)
        merged.append(item)
    return merged


def _merge_educations(base: list[Any], incoming: list[Any]) -> list[Any]:
    """Merge imported education entries by institution/degree key."""

    merged = list(base)
    existing_keys = {(item.institution.lower(), item.degree.lower()) for item in merged}
    for item in incoming:
        key = (item.institution.lower(), item.degree.lower())
        if key in existing_keys:
            continue
        existing_keys.add(key)
        merged.append(item)
    return merged


def _merge_skills(base: list[Any], incoming: list[Any]) -> list[Any]:
    """Merge imported skill entries by lower-case skill name."""

    merged = list(base)
    existing_names = {item.skill_name.lower() for item in merged}
    for item in incoming:
        key = item.skill_name.lower()
        if key in existing_names:
            continue
        existing_names.add(key)
        merged.append(item)
    return merged


def _merge_unmapped_candidates(base: list[Any], incoming: list[Any]) -> list[Any]:
    """Merge unmapped candidates by normalized text key."""

    merged = list(base)
    existing_keys = {str(item.text).strip().lower() for item in merged}
    for item in incoming:
        key = str(item.text).strip().lower()
        if not key or key in existing_keys:
            continue
        existing_keys.add(key)
        merged.append(item)
    return merged


def _build_profile_apply_payload(existing_profile_payload: dict[str, object] | None) -> dict[str, Any]:
    """Build mutable payload used for apply merge operations."""

    if existing_profile_payload is None:
        return {
            "full_name": "",
            "email": "",
            "phone": None,
            "location": None,
            "headline": None,
            "summary": None,
            "experiences": [],
            "educations": [],
            "skills": [],
        }

    active_version = existing_profile_payload.get("active_version")
    if not isinstance(active_version, dict):
        return {
            "full_name": "",
            "email": "",
            "phone": None,
            "location": None,
            "headline": None,
            "summary": None,
            "experiences": [],
            "educations": [],
            "skills": [],
        }

    return {
        "full_name": str(active_version.get("full_name", "")),
        "email": str(active_version.get("email", "")),
        "phone": _optional_string(active_version.get("phone")),
        "location": _optional_string(active_version.get("location")),
        "headline": _optional_string(active_version.get("headline")),
        "summary": _optional_string(active_version.get("summary")),
        "experiences": [
            {
                "company": str(item.get("company", "")),
                "title": str(item.get("title", "")),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "description": item.get("description"),
            }
            for item in active_version.get("experiences", [])
            if isinstance(item, dict)
        ],
        "educations": [
            {
                "institution": str(item.get("institution", "")),
                "degree": str(item.get("degree", "")),
                "field_of_study": item.get("field_of_study"),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
            }
            for item in active_version.get("educations", [])
            if isinstance(item, dict)
        ],
        "skills": [
            {
                "skill_name": str(item.get("skill_name", "")),
                "level": item.get("level"),
                "category": item.get("category"),
            }
            for item in active_version.get("skills", [])
            if isinstance(item, dict)
        ],
    }


def _apply_scalar_fields(
    *,
    payload: dict[str, Any],
    fields: list[Any],
    applied_field_paths: list[tuple[str, str]],
) -> None:
    """Apply scalar field decisions into payload."""

    scalar_fields = {"full_name", "email", "phone", "location", "headline", "summary"}
    for field in fields:
        if field.field_path not in scalar_fields:
            continue
        if field.suggested_value is None:
            continue
        payload[field.field_path] = field.suggested_value
        applied_field_paths.append((field.field_path, field.suggested_value))


def _apply_experience_fields(
    *,
    payload: dict[str, Any],
    fields: list[Any],
    applied_field_paths: list[tuple[str, str]],
) -> None:
    """Apply experience field decisions into payload list."""

    grouped: dict[int, dict[str, str]] = {}
    for field in fields:
        parsed = _parse_indexed_field_path(field.field_path)
        if parsed is None or parsed[0] != "experiences":
            continue
        _, index, field_name = parsed
        grouped.setdefault(index, {})[field_name] = field.suggested_value or ""

    existing_pairs = {
        (item.get("company", "").strip().lower(), item.get("title", "").strip().lower())
        for item in payload["experiences"]
    }

    for source_index in sorted(grouped):
        row = grouped[source_index]
        company = row.get("company", "").strip()
        title = row.get("title", "").strip()
        if not company or not title:
            continue

        key = (company.lower(), title.lower())
        if key in existing_pairs:
            continue

        existing_pairs.add(key)
        entry = ExperienceInput(
            company=company,
            title=title,
            start_date=_optional_date_string(row.get("start_date")),
            end_date=_optional_date_string(row.get("end_date")),
            description=_optional_string(row.get("description")),
        )
        payload["experiences"].append(entry.model_dump(mode="json"))

        for field_name, value in row.items():
            if not value:
                continue
            applied_field_paths.append((f"experiences[{source_index}].{field_name}", value))


def _apply_education_fields(
    *,
    payload: dict[str, Any],
    fields: list[Any],
    applied_field_paths: list[tuple[str, str]],
) -> None:
    """Apply education field decisions into payload list."""

    grouped: dict[int, dict[str, str]] = {}
    for field in fields:
        parsed = _parse_indexed_field_path(field.field_path)
        if parsed is None or parsed[0] != "educations":
            continue
        _, index, field_name = parsed
        grouped.setdefault(index, {})[field_name] = field.suggested_value or ""

    existing_pairs = {
        (item.get("institution", "").strip().lower(), item.get("degree", "").strip().lower())
        for item in payload["educations"]
    }

    for source_index in sorted(grouped):
        row = grouped[source_index]
        institution = row.get("institution", "").strip()
        degree = row.get("degree", "").strip()
        if not institution or not degree:
            continue

        key = (institution.lower(), degree.lower())
        if key in existing_pairs:
            continue

        existing_pairs.add(key)
        entry = EducationInput(
            institution=institution,
            degree=degree,
            field_of_study=_optional_string(row.get("field_of_study")),
            start_date=_optional_date_string(row.get("start_date")),
            end_date=_optional_date_string(row.get("end_date")),
        )
        payload["educations"].append(entry.model_dump(mode="json"))

        for field_name, value in row.items():
            if not value:
                continue
            applied_field_paths.append((f"educations[{source_index}].{field_name}", value))


def _apply_skill_fields(
    *,
    payload: dict[str, Any],
    fields: list[Any],
    applied_field_paths: list[tuple[str, str]],
) -> None:
    """Apply skill field decisions into payload list."""

    grouped: dict[int, dict[str, str]] = {}
    for field in fields:
        parsed = _parse_indexed_field_path(field.field_path)
        if parsed is None or parsed[0] != "skills":
            continue
        _, index, field_name = parsed
        grouped.setdefault(index, {})[field_name] = field.suggested_value or ""

    existing_names = {item.get("skill_name", "").strip().lower() for item in payload["skills"]}

    for source_index in sorted(grouped):
        row = grouped[source_index]
        skill_name = row.get("skill_name", "").strip()
        if not skill_name:
            continue

        key = skill_name.lower()
        if key in existing_names:
            continue

        existing_names.add(key)
        entry = SkillInput(
            skill_name=skill_name,
            level=_optional_string(row.get("level")),
            category=_optional_string(row.get("category")),
        )
        payload["skills"].append(entry.model_dump(mode="json"))

        for field_name, value in row.items():
            if not value:
                continue
            applied_field_paths.append((f"skills[{source_index}].{field_name}", value))


def _parse_indexed_field_path(field_path: str) -> tuple[str, int, str] | None:
    """Parse indexed section field path values."""

    match = _INDEXED_PATH_PATTERN.match(field_path)
    if match is None:
        return None

    section = match.group("section")
    index = int(match.group("index"))
    field_name = match.group("field")
    return section, index, field_name


def _optional_string(value: object) -> str | None:
    """Return non-empty string representation for optional values."""

    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _optional_date_string(value: str | None) -> str | None:
    """Return ISO date string when it matches ``YYYY-MM-DD``."""

    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
        return None
    return candidate


def _format_validation_error(exc: ValidationError) -> str:
    """Format pydantic validation errors into an apply-friendly message.

    Args:
        exc: Raised pydantic validation error.

    Returns:
        Human-readable validation message for API responses.
    """

    details: list[str] = []
    for row in exc.errors():
        location = ".".join(str(part) for part in row.get("loc", ()))
        message = str(row.get("msg", "invalid value"))
        if location:
            details.append(f"{location}: {message}")
        else:
            details.append(message)

    summary = "; ".join(details[:3]) if details else "Invalid imported field values."
    return f"Import apply validation failed. Review extracted fields: {summary}"


def _delete_source_file(file_path: str | None) -> None:
    """Delete one persisted import source file path when present.

    Args:
        file_path: Persisted source file path.

    Returns:
        None.
    """

    if not file_path:
        return

    try:
        Path(file_path).unlink(missing_ok=True)
    except OSError:
        return


_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+./#-]*")


def _truncate_for_llm_input(*, raw_text: str, max_chars: int) -> str:
    """Return length-limited source text for LLM extraction.

    Args:
        raw_text: Full extracted source text.
        max_chars: Maximum character count.

    Returns:
        Trimmed source text.
    """

    cleaned = raw_text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


def _build_profile_draft_from_llm_response(
    *,
    response: ProfileImportExtractionResponse,
    source_locator: str,
) -> ImportedProfileDraft:
    """Build imported profile draft from structured LLM response.

    Args:
        response: Structured LLM extraction response.
        source_locator: Default source locator.

    Returns:
        Imported profile draft.
    """

    full_name = _extract_scalar_value(response.full_name, max_length=120)
    email = _extract_scalar_value(response.email, max_length=255)
    phone = _extract_scalar_value(response.phone, max_length=64)
    location = _extract_scalar_value(response.location, max_length=120)
    headline = _extract_scalar_value(response.headline, max_length=220)
    summary = _extract_scalar_value(response.summary, max_length=1200)

    experiences: list[ImportedExperienceDraft] = []
    for item in response.experiences:
        company = _normalize_value(item.company, max_length=160)
        title = _normalize_value(item.title, max_length=160)
        if not company or not title:
            continue

        experiences.append(
            ImportedExperienceDraft(
                company=company,
                title=title,
                start_date=_normalize_value(item.start_date, max_length=32),
                end_date=_normalize_value(item.end_date, max_length=32),
                description=_normalize_value(item.description, max_length=1200),
                source_locator=_normalize_value(item.source_locator, max_length=255) or source_locator,
                source_excerpt=_normalize_value(item.source_excerpt, max_length=1200),
            )
        )

    educations: list[ImportedEducationDraft] = []
    for item in response.educations:
        institution = _normalize_value(item.institution, max_length=160)
        degree = _normalize_value(item.degree, max_length=160)
        if not institution or not degree:
            continue

        educations.append(
            ImportedEducationDraft(
                institution=institution,
                degree=degree,
                field_of_study=_normalize_value(item.field_of_study, max_length=160),
                start_date=_normalize_value(item.start_date, max_length=32),
                end_date=_normalize_value(item.end_date, max_length=32),
                source_locator=_normalize_value(item.source_locator, max_length=255) or source_locator,
                source_excerpt=_normalize_value(item.source_excerpt, max_length=1200),
            )
        )

    skills: list[ImportedSkillDraft] = []
    for item in response.skills:
        skill_name = _normalize_value(item.skill_name, max_length=80)
        if not skill_name:
            continue

        skills.append(
            ImportedSkillDraft(
                skill_name=skill_name,
                level=_normalize_value(item.level, max_length=40),
                category=_normalize_value(item.category, max_length=80),
                source_locator=_normalize_value(item.source_locator, max_length=255) or source_locator,
                source_excerpt=_normalize_value(item.source_excerpt, max_length=1200),
            )
        )

    return ImportedProfileDraft(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        headline=headline,
        summary=summary,
        experiences=experiences,
        educations=educations,
        skills=skills,
    )


def _filter_profile_draft_by_source_support(
    *,
    draft: ImportedProfileDraft,
    raw_text: str,
) -> ImportedProfileDraft:
    """Filter LLM draft values that are not text-supported by the source.

    Args:
        draft: LLM-derived profile draft.
        raw_text: Original extracted source text.

    Returns:
        Filtered profile draft containing only source-supported values.
    """

    normalized_source = normalize_text(raw_text).lower()
    source_tokens = set(_TOKEN_PATTERN.findall(normalized_source))

    full_name = _supported_scalar_value(draft.full_name, normalized_source, source_tokens)
    email = _supported_scalar_value(draft.email, normalized_source, source_tokens)
    phone = _supported_scalar_value(draft.phone, normalized_source, source_tokens)
    location = _supported_scalar_value(draft.location, normalized_source, source_tokens)
    headline = _supported_scalar_value(draft.headline, normalized_source, source_tokens)
    summary = _supported_scalar_value(draft.summary, normalized_source, source_tokens)

    experiences: list[ImportedExperienceDraft] = []
    for item in draft.experiences:
        company = _supported_scalar_value(item.company, normalized_source, source_tokens)
        title = _supported_scalar_value(item.title, normalized_source, source_tokens)
        if not company or not title:
            continue
        if len(company.split()) > 10 or len(title.split()) > 10:
            continue

        experiences.append(
            ImportedExperienceDraft(
                company=company,
                title=title,
                start_date=_supported_scalar_value(item.start_date, normalized_source, source_tokens),
                end_date=_supported_scalar_value(item.end_date, normalized_source, source_tokens),
                description=_supported_scalar_value(item.description, normalized_source, source_tokens),
                source_locator=item.source_locator,
                source_excerpt=_supported_scalar_value(item.source_excerpt, normalized_source, source_tokens),
            )
        )

    educations: list[ImportedEducationDraft] = []
    for item in draft.educations:
        institution = _supported_scalar_value(item.institution, normalized_source, source_tokens)
        degree = _supported_scalar_value(item.degree, normalized_source, source_tokens)
        if not institution or not degree:
            continue

        educations.append(
            ImportedEducationDraft(
                institution=institution,
                degree=degree,
                field_of_study=_supported_scalar_value(item.field_of_study, normalized_source, source_tokens),
                start_date=_supported_scalar_value(item.start_date, normalized_source, source_tokens),
                end_date=_supported_scalar_value(item.end_date, normalized_source, source_tokens),
                source_locator=item.source_locator,
                source_excerpt=_supported_scalar_value(item.source_excerpt, normalized_source, source_tokens),
            )
        )

    skills: list[ImportedSkillDraft] = []
    for item in draft.skills:
        skill_name = _supported_scalar_value(item.skill_name, normalized_source, source_tokens)
        if not skill_name:
            continue
        if len(skill_name.split()) > 6:
            continue

        skills.append(
            ImportedSkillDraft(
                skill_name=skill_name,
                level=_supported_scalar_value(item.level, normalized_source, source_tokens),
                category=_supported_scalar_value(item.category, normalized_source, source_tokens),
                source_locator=item.source_locator,
                source_excerpt=_supported_scalar_value(item.source_excerpt, normalized_source, source_tokens),
            )
        )

    return ImportedProfileDraft(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        headline=headline,
        summary=summary,
        experiences=experiences,
        educations=educations,
        skills=skills,
        unmapped_candidates=list(draft.unmapped_candidates),
    )


def _supported_scalar_value(
    value: str | None,
    normalized_source: str,
    source_tokens: set[str],
) -> str | None:
    """Return value only when it is supported by source text.

    Args:
        value: Candidate value.
        normalized_source: Lower-cased normalized source text.
        source_tokens: Token set built from source text.

    Returns:
        Supported value or ``None`` when unsupported.
    """

    normalized_value = _normalize_value(value, max_length=1200)
    if not normalized_value:
        return None

    if _is_supported_value(
        value=normalized_value,
        normalized_source=normalized_source,
        source_tokens=source_tokens,
    ):
        return normalized_value

    return None


def _is_supported_value(
    *,
    value: str,
    normalized_source: str,
    source_tokens: set[str],
) -> bool:
    """Return whether one value is directly supported by source text.

    Args:
        value: Candidate value.
        normalized_source: Lower-cased normalized source text.
        source_tokens: Token set built from source text.

    Returns:
        True when value appears directly or with strong token overlap.
    """

    normalized_value = normalize_text(value).lower()
    if not normalized_value:
        return False

    if normalized_value in normalized_source:
        return True

    value_tokens = _TOKEN_PATTERN.findall(normalized_value)
    if not value_tokens:
        return False

    if len(value_tokens) == 1:
        return value_tokens[0] in source_tokens

    overlap = sum(1 for token in value_tokens if token in source_tokens)
    ratio = overlap / len(value_tokens)
    return ratio >= 0.75


def _extract_scalar_value(
    field: ProfileImportScalarField | None,
    *,
    max_length: int,
) -> str | None:
    """Extract scalar value from profile import scalar field model.

    Args:
        field: Scalar field model.
        max_length: Maximum allowed length.

    Returns:
        Normalized scalar value.
    """

    if field is None:
        return None
    return _normalize_value(field.value, max_length=max_length)


def _normalize_value(value: str | None, *, max_length: int) -> str | None:
    """Normalize and clamp one extracted value.

    Args:
        value: Raw value.
        max_length: Maximum allowed length.

    Returns:
        Cleaned value or ``None`` when empty.
    """

    if value is None:
        return None
    normalized = normalize_text(value)
    if not normalized:
        return None
    return normalized[:max_length]


def _is_empty_import_draft(draft: ImportedProfileDraft) -> bool:
    """Return whether an imported draft has no usable fields.

    Args:
        draft: Imported draft.

    Returns:
        True when no scalar or section rows are present.
    """

    scalar_values = (
        draft.full_name,
        draft.email,
        draft.phone,
        draft.location,
        draft.headline,
        draft.summary,
    )
    if any(item for item in scalar_values):
        return False
    if draft.experiences:
        return False
    if draft.educations:
        return False
    if draft.skills:
        return False
    return True
