"""Service for reproducible application package orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models.application_package import ApplicationPackageModel
from app.db.models.document import DocumentArtifactModel
from app.db.models.job import JobAnalysisModel, JobPostModel
from app.db.models.tailoring import ProfileSnapshotModel, TailoringPlanModel
from app.db.repositories.application_package_repository import (
    ApplicationPackageCreatePayload,
    ApplicationPackageDocumentPayload,
    ApplicationPackageEventPayload,
    ApplicationPackageRepository,
)
from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.job_repository import JobAnalysisRepository, JobPostRepository
from app.db.repositories.tailoring_repository import TailoringRepository
from app.schemas.application_package import (
    ApplicationPackageCreateRequest,
    ApplicationPackageDocumentResponse,
    ApplicationPackageEventResponse,
    ApplicationPackageListResponse,
    ApplicationPackageResponse,
)


class ApplicationPackageNotFoundError(Exception):
    """Raised when an application package cannot be found."""


class ApplicationPackageDependencyError(Exception):
    """Raised when dependent entities for package creation are missing."""


class ApplicationPackageValidationError(Exception):
    """Raised when package linkage validation fails."""


class ApplicationPackageService:
    """Service coordinating package reproducibility and persistence."""

    def __init__(self, session: Session) -> None:
        """Initialize service with repository dependencies.

        Args:
            session: Active SQLAlchemy session.
        """

        self._session = session
        self._package_repository = ApplicationPackageRepository(session)
        self._job_post_repository = JobPostRepository(session)
        self._analysis_repository = JobAnalysisRepository(session)
        self._tailoring_repository = TailoringRepository(session)
        self._document_repository = DocumentRepository(session)

    def create_package(self, request: ApplicationPackageCreateRequest) -> ApplicationPackageResponse:
        """Create and persist a reproducible application package.

        Args:
            request: Package creation request.

        Returns:
            Persisted application package response.

        Raises:
            ApplicationPackageDependencyError: If required entities are missing.
            ApplicationPackageValidationError: If entity linkage is invalid.
        """

        job_post = self._require_job_post(request.job_post_id)
        analysis = self._require_analysis(request.job_analysis_id)
        plan = self._require_plan(request.tailoring_plan_id)
        snapshot = self._require_snapshot(request.profile_snapshot_id)
        artifacts = self._load_artifacts(request.document_artifact_ids)

        self._validate_linkage(
            job_post=job_post,
            analysis=analysis,
            plan=plan,
            snapshot=snapshot,
            artifacts=artifacts,
        )

        document_payloads = [self._to_document_payload(item) for item in artifacts]
        event_payloads = self._build_initial_event_payloads(
            snapshot_id=snapshot.id,
            artifact_count=len(document_payloads),
        )

        package = self._package_repository.create_package(
            ApplicationPackageCreatePayload(
                job_post_id=job_post.id,
                job_analysis_id=analysis.id,
                tailoring_plan_id=plan.id,
                profile_snapshot_id=snapshot.id,
                language=snapshot.target_language,
                status="created",
                documents=document_payloads,
                events=event_payloads,
            )
        )
        self._session.commit()
        return self._to_response(package)

    def get_package(self, package_id: str) -> ApplicationPackageResponse:
        """Retrieve one application package by identifier.

        Args:
            package_id: Package identifier.

        Returns:
            Application package response.

        Raises:
            ApplicationPackageNotFoundError: If package does not exist.
        """

        package = self._package_repository.get_package(package_id)
        if package is None:
            raise ApplicationPackageNotFoundError("Application package not found.")
        return self._to_response(package)

    def list_packages(self) -> ApplicationPackageListResponse:
        """List all application packages.

        Returns:
            Package list response.
        """

        packages = [self._to_response(item) for item in self._package_repository.list_packages()]
        return ApplicationPackageListResponse(packages=packages)

    def _require_job_post(self, job_post_id: str) -> JobPostModel:
        """Load required job post entity.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Job post model.

        Raises:
            ApplicationPackageDependencyError: If job post is missing.
        """

        model = self._job_post_repository.get(job_post_id)
        if model is None:
            raise ApplicationPackageDependencyError("Job post not found.")
        return model

    def _require_analysis(self, analysis_id: str) -> JobAnalysisModel:
        """Load required job analysis entity.

        Args:
            analysis_id: Job analysis identifier.

        Returns:
            Job analysis model.

        Raises:
            ApplicationPackageDependencyError: If analysis is missing.
        """

        model = self._analysis_repository.get(analysis_id)
        if model is None:
            raise ApplicationPackageDependencyError("Job analysis not found.")
        return model

    def _require_plan(self, plan_id: str) -> TailoringPlanModel:
        """Load required tailoring plan entity.

        Args:
            plan_id: Tailoring plan identifier.

        Returns:
            Tailoring plan model.

        Raises:
            ApplicationPackageDependencyError: If plan is missing.
        """

        model = self._tailoring_repository.get_plan(plan_id)
        if model is None:
            raise ApplicationPackageDependencyError("Tailoring plan not found.")
        return model

    def _require_snapshot(self, snapshot_id: str) -> ProfileSnapshotModel:
        """Load required tailored profile snapshot entity.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Profile snapshot model.

        Raises:
            ApplicationPackageDependencyError: If snapshot is missing.
        """

        model = self._tailoring_repository.get_snapshot(snapshot_id)
        if model is None:
            raise ApplicationPackageDependencyError("Profile snapshot not found.")
        return model

    def _load_artifacts(self, artifact_ids: list[str]) -> list[DocumentArtifactModel]:
        """Load and validate artifact references.

        Args:
            artifact_ids: Artifact identifier list.

        Returns:
            Loaded artifact models.

        Raises:
            ApplicationPackageDependencyError: If any artifact is missing.
        """

        models: list[DocumentArtifactModel] = []
        for artifact_id in self._deduplicate_artifact_ids(artifact_ids):
            model = self._document_repository.get_artifact(artifact_id)
            if model is None:
                raise ApplicationPackageDependencyError(f"Document artifact not found: {artifact_id}")
            models.append(model)
        return models

    @staticmethod
    def _deduplicate_artifact_ids(artifact_ids: list[str]) -> list[str]:
        """Return artifact identifiers deduplicated in first-seen order.

        Args:
            artifact_ids: Requested artifact identifiers.

        Returns:
            Deduplicated artifact identifier list.
        """

        unique_ids: list[str] = []
        seen: set[str] = set()
        for artifact_id in artifact_ids:
            if artifact_id in seen:
                continue
            seen.add(artifact_id)
            unique_ids.append(artifact_id)
        return unique_ids

    @staticmethod
    def _validate_linkage(
        *,
        job_post: JobPostModel,
        analysis: JobAnalysisModel,
        plan: TailoringPlanModel,
        snapshot: ProfileSnapshotModel,
        artifacts: list[DocumentArtifactModel],
    ) -> None:
        """Validate package linkage for reproducibility.

        Args:
            job_post: Job post entity.
            analysis: Job analysis entity.
            plan: Tailoring plan entity.
            snapshot: Tailored snapshot entity.
            artifacts: Document artifact entities.

        Raises:
            ApplicationPackageValidationError: If linkage constraints fail.
        """

        if analysis.job_post_id != job_post.id:
            raise ApplicationPackageValidationError("Job analysis does not belong to job post.")
        if plan.job_analysis_id != analysis.id:
            raise ApplicationPackageValidationError("Tailoring plan does not belong to analysis.")
        if snapshot.tailoring_plan_id != plan.id:
            raise ApplicationPackageValidationError("Profile snapshot does not belong to tailoring plan.")

        for artifact in artifacts:
            if artifact.snapshot_id != snapshot.id:
                raise ApplicationPackageValidationError(
                    "Document artifact does not belong to selected profile snapshot."
                )

    @staticmethod
    def _build_initial_event_payloads(
        *,
        snapshot_id: str,
        artifact_count: int,
    ) -> list[ApplicationPackageEventPayload]:
        """Build initial audit events for package creation.

        Args:
            snapshot_id: Snapshot identifier linked to package.
            artifact_count: Number of linked artifacts.

        Returns:
            Ordered event payload list.
        """

        return [
            ApplicationPackageEventPayload(
                event_type="package_created",
                message=f"Created package with snapshot {snapshot_id}.",
            ),
            ApplicationPackageEventPayload(
                event_type="documents_linked",
                message=f"Linked {artifact_count} document artifacts.",
            ),
        ]

    @staticmethod
    def _to_document_payload(artifact: DocumentArtifactModel) -> ApplicationPackageDocumentPayload:
        """Map document artifact model to package document payload.

        Args:
            artifact: Document artifact model.

        Returns:
            Package document payload.
        """

        checksum = _compute_sha256_if_exists(Path(artifact.file_path))
        return ApplicationPackageDocumentPayload(
            artifact_id=artifact.id,
            document_type=artifact.document_type,
            language=artifact.language,
            file_format=artifact.file_format,
            file_name=artifact.file_name,
            file_path=artifact.file_path,
            file_size_bytes=artifact.file_size_bytes,
            checksum_sha256=checksum,
        )

    @staticmethod
    def _to_response(package: ApplicationPackageModel) -> ApplicationPackageResponse:
        """Map package ORM model to API response.

        Args:
            package: Package ORM model.

        Returns:
            Package response schema.
        """

        documents = [
            ApplicationPackageDocumentResponse(
                id=item.id,
                artifact_id=item.artifact_id,
                document_type=item.document_type,
                language=item.language,
                file_format=item.file_format,
                file_name=item.file_name,
                file_size_bytes=item.file_size_bytes,
                checksum_sha256=item.checksum_sha256,
                created_at=item.created_at,
            )
            for item in package.documents
        ]
        events = [
            ApplicationPackageEventResponse(
                id=item.id,
                event_type=item.event_type,
                message=item.message,
                created_at=item.created_at,
            )
            for item in package.events
        ]

        return ApplicationPackageResponse(
            id=package.id,
            job_post_id=package.job_post_id,
            job_analysis_id=package.job_analysis_id,
            tailoring_plan_id=package.tailoring_plan_id,
            profile_snapshot_id=package.profile_snapshot_id,
            language=package.language,
            status=package.status,
            created_at=package.created_at,
            documents=documents,
            events=events,
        )


def _compute_sha256_if_exists(file_path: Path) -> str | None:
    """Compute SHA256 checksum for an existing file path.

    Args:
        file_path: Artifact file path.

    Returns:
        Hex digest when file exists, otherwise None.
    """

    if not file_path.exists() or not file_path.is_file():
        return None

    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
