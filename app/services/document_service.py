"""Service for rendering, exporting, and persisting document artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.document import DocumentArtifactModel
from app.db.models.tailoring import ProfileSnapshotModel
from app.db.repositories.document_repository import DocumentArtifactCreatePayload, DocumentRepository
from app.db.repositories.job_repository import JobAnalysisRepository, JobPostRepository
from app.db.repositories.tailoring_repository import TailoringRepository
from app.documents.exporters import export_docx, export_html, export_pdf
from app.documents.html_renderer import render_cover_letter_html, render_cv_html
from app.schemas.document import (
    DocumentArtifactListResponse,
    DocumentArtifactResponse,
    DocumentGenerateRequest,
    DocumentGenerateResponse,
)

DocumentType = Literal["cv", "cover_letter"]
DocumentFormat = Literal["html", "pdf", "docx"]

_MIME_TYPES: dict[str, str] = {
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentDependencyNotFoundError(Exception):
    """Raised when required snapshot or upstream data is missing."""


class DocumentArtifactNotFoundError(Exception):
    """Raised when requested document artifact does not exist."""


class DocumentFileMissingError(Exception):
    """Raised when persisted artifact metadata points to missing file."""


class DocumentService:
    """Service coordinating document rendering and artifact persistence."""

    def __init__(self, session: Session, storage_dir: Path | None = None) -> None:
        """Initialize service with repository dependencies.

        Args:
            session: Active SQLAlchemy session.
            storage_dir: Optional local directory for generated files.
        """

        self._session = session
        self._tailoring_repository = TailoringRepository(session)
        self._analysis_repository = JobAnalysisRepository(session)
        self._job_post_repository = JobPostRepository(session)
        self._document_repository = DocumentRepository(session)

        if storage_dir is None:
            settings = get_settings()
            storage_dir = Path(settings.document_storage_dir)
        self._storage_dir = storage_dir

    def generate_cv(self, request: DocumentGenerateRequest) -> DocumentGenerateResponse:
        """Generate CV artifacts for a tailored snapshot.

        Args:
            request: Document generation request.

        Returns:
            Generated CV artifact response.

        Raises:
            DocumentDependencyNotFoundError: If source snapshot is missing.
        """

        return self._generate_documents(request=request, document_type="cv")

    def generate_cover_letter(self, request: DocumentGenerateRequest) -> DocumentGenerateResponse:
        """Generate cover letter artifacts for a tailored snapshot.

        Args:
            request: Document generation request.

        Returns:
            Generated cover letter artifact response.

        Raises:
            DocumentDependencyNotFoundError: If source snapshot or related job data is missing.
        """

        return self._generate_documents(request=request, document_type="cover_letter")

    def get_artifact(self, artifact_id: str) -> DocumentArtifactResponse:
        """Get one generated document artifact by identifier.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Document artifact response.

        Raises:
            DocumentArtifactNotFoundError: If artifact does not exist.
        """

        model = self._document_repository.get_artifact(artifact_id)
        if model is None:
            raise DocumentArtifactNotFoundError("Document artifact not found.")
        return self._to_artifact_response(model)

    def list_snapshot_artifacts(self, snapshot_id: str) -> DocumentArtifactListResponse:
        """List all artifacts for a tailored snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Artifact listing response.

        Raises:
            DocumentDependencyNotFoundError: If snapshot does not exist.
        """

        snapshot = self._tailoring_repository.get_snapshot(snapshot_id)
        if snapshot is None:
            raise DocumentDependencyNotFoundError("Tailored snapshot not found.")

        artifacts = [
            self._to_artifact_response(item)
            for item in self._document_repository.list_by_snapshot(snapshot_id)
        ]
        return DocumentArtifactListResponse(snapshot_id=snapshot_id, artifacts=artifacts)

    def get_artifact_file(self, artifact_id: str) -> tuple[Path, str, str]:
        """Resolve local file info for artifact download.

        Args:
            artifact_id: Artifact identifier.

        Returns:
            Tuple of file path, mime type, and file name.

        Raises:
            DocumentArtifactNotFoundError: If artifact metadata does not exist.
            DocumentFileMissingError: If metadata file path is missing on disk.
        """

        model = self._document_repository.get_artifact(artifact_id)
        if model is None:
            raise DocumentArtifactNotFoundError("Document artifact not found.")

        file_path = Path(model.file_path)
        if not file_path.exists():
            raise DocumentFileMissingError("Document file is missing from storage.")

        return file_path, model.mime_type, model.file_name

    def _generate_documents(
        self,
        *,
        request: DocumentGenerateRequest,
        document_type: DocumentType,
    ) -> DocumentGenerateResponse:
        """Generate one document type and persist selected artifact formats.

        Args:
            request: Document generation request.
            document_type: Logical document type.

        Returns:
            Generation response containing persisted artifacts.

        Raises:
            DocumentDependencyNotFoundError: If required source entities are missing.
        """

        snapshot = self._tailoring_repository.get_snapshot(request.snapshot_id)
        if snapshot is None:
            raise DocumentDependencyNotFoundError("Tailored snapshot not found.")

        language = request.language or snapshot.target_language
        formats = self._normalize_formats(request.formats)

        html_content = self._render_html(snapshot=snapshot, language=language, document_type=document_type)

        artifacts: list[DocumentArtifactResponse] = []
        for file_format in formats:
            output_path = self._build_output_path(
                snapshot_id=snapshot.id,
                document_type=document_type,
                language=language,
                file_format=file_format,
            )
            self._export_file(file_format=file_format, html_content=html_content, output_path=output_path)
            artifact = self._document_repository.create_artifact(
                DocumentArtifactCreatePayload(
                    snapshot_id=snapshot.id,
                    document_type=document_type,
                    language=language,
                    file_format=file_format,
                    mime_type=_MIME_TYPES[file_format],
                    file_name=output_path.name,
                    file_path=str(output_path.resolve()),
                    file_size_bytes=output_path.stat().st_size,
                )
            )
            artifacts.append(self._to_artifact_response(artifact))

        self._session.commit()
        return DocumentGenerateResponse(
            snapshot_id=snapshot.id,
            document_type=document_type,
            artifacts=artifacts,
        )

    def _render_html(
        self,
        *,
        snapshot: ProfileSnapshotModel,
        language: str,
        document_type: DocumentType,
    ) -> str:
        """Render document HTML for a snapshot and language.

        Args:
            snapshot: Source snapshot model.
            language: Language code.
            document_type: Logical document type.

        Returns:
            Rendered HTML string.

        Raises:
            DocumentDependencyNotFoundError: If cover letter requires missing upstream entities.
        """

        context = self._build_snapshot_context(snapshot)
        if document_type == "cv":
            return render_cv_html(language=language, context=context)

        job_context = self._resolve_job_context(snapshot)
        context.update(job_context)
        return render_cover_letter_html(language=language, context=context)

    def _resolve_job_context(self, snapshot: ProfileSnapshotModel) -> dict[str, str]:
        """Resolve job title and company context for cover letters.

        Args:
            snapshot: Source tailored snapshot.

        Returns:
            Job metadata dictionary.

        Raises:
            DocumentDependencyNotFoundError: If job context cannot be resolved.
        """

        plan = self._tailoring_repository.get_plan(snapshot.tailoring_plan_id)
        if plan is None:
            raise DocumentDependencyNotFoundError("Tailoring plan not found for snapshot.")

        analysis = self._analysis_repository.get(plan.job_analysis_id)
        if analysis is None:
            raise DocumentDependencyNotFoundError("Job analysis not found for tailoring plan.")

        job_post = self._job_post_repository.get(analysis.job_post_id)
        if job_post is None:
            raise DocumentDependencyNotFoundError("Job post not found for analysis.")

        return {
            "job_title": job_post.title,
            "company": job_post.company or "",
        }

    @staticmethod
    def _build_snapshot_context(snapshot: ProfileSnapshotModel) -> dict[str, object]:
        """Build Jinja2 render context from snapshot model.

        Args:
            snapshot: Source snapshot model.

        Returns:
            Template context dictionary.
        """

        return {
            "full_name": snapshot.full_name,
            "email": snapshot.email,
            "phone": snapshot.phone,
            "location": snapshot.location,
            "headline": snapshot.headline,
            "summary": snapshot.summary,
            "experiences": [
                {
                    "company": item.company,
                    "title": item.title,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "description": item.description,
                }
                for item in snapshot.experiences
            ],
            "educations": [
                {
                    "institution": item.institution,
                    "degree": item.degree,
                    "field_of_study": item.field_of_study,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                }
                for item in snapshot.educations
            ],
            "skills": [
                {
                    "skill_name": item.skill_name,
                    "level": item.level,
                    "category": item.category,
                }
                for item in snapshot.skills
            ],
        }

    def _build_output_path(
        self,
        *,
        snapshot_id: str,
        document_type: DocumentType,
        language: str,
        file_format: DocumentFormat,
    ) -> Path:
        """Build output path for generated artifact file.

        Args:
            snapshot_id: Snapshot identifier.
            document_type: Logical document type.
            language: Language code.
            file_format: Output format.

        Returns:
            Artifact output path.
        """

        directory = self._storage_dir / snapshot_id
        directory.mkdir(parents=True, exist_ok=True)
        file_name = f"{document_type}_{language}_{uuid4().hex}.{file_format}"
        return directory / file_name

    @staticmethod
    def _export_file(*, file_format: DocumentFormat, html_content: str, output_path: Path) -> None:
        """Export rendered HTML into selected file format.

        Args:
            file_format: Output format.
            html_content: Rendered HTML content.
            output_path: Artifact output path.
        """

        if file_format == "html":
            export_html(html_content, output_path)
            return
        if file_format == "pdf":
            export_pdf(html_content, output_path)
            return
        export_docx(html_content, output_path)

    @staticmethod
    def _normalize_formats(formats: list[str]) -> list[DocumentFormat]:
        """Normalize requested document formats while preserving order.

        Args:
            formats: Requested format list.

        Returns:
            Deduplicated and validated format sequence.
        """

        allowed: dict[str, DocumentFormat] = {"html": "html", "pdf": "pdf", "docx": "docx"}
        normalized: list[DocumentFormat] = []
        seen: set[DocumentFormat] = set()

        for file_format in formats:
            normalized_format = allowed.get(file_format)
            if normalized_format is None:
                continue
            if normalized_format in seen:
                continue
            seen.add(normalized_format)
            normalized.append(normalized_format)

        if not normalized:
            return ["pdf", "docx"]
        return normalized

    @staticmethod
    def _to_artifact_response(model: DocumentArtifactModel) -> DocumentArtifactResponse:
        """Map artifact ORM model to API response schema.

        Args:
            model: Artifact ORM model.

        Returns:
            Artifact response schema.
        """

        return DocumentArtifactResponse(
            id=model.id,
            snapshot_id=model.snapshot_id,
            document_type=model.document_type,
            language=model.language,
            file_format=model.file_format,
            mime_type=model.mime_type,
            file_name=model.file_name,
            file_size_bytes=model.file_size_bytes,
            created_at=model.created_at,
        )
