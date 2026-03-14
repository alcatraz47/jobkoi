"""Unit tests for document generation service behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.schemas.document import DocumentGenerateRequest
from app.schemas.job import JobAnalysisCreateRequest, JobPostCreateRequest
from app.schemas.profile import MasterProfileCreateRequest
from app.schemas.tailoring import TailoredSnapshotCreateRequest, TailoringPlanCreateRequest
from app.services.document_service import (
    DocumentArtifactNotFoundError,
    DocumentFileMissingError,
    DocumentService,
)
from app.services.job_analysis_service import JobAnalysisService
from app.services.job_post_service import JobPostService
from app.services.profile_service import ProfileService
from app.services.tailoring_service import TailoringService


def test_document_service_generates_and_persists_cv_artifacts(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Service should render, export, and persist CV artifacts."""

    snapshot_id = _create_snapshot(db_session)
    service = DocumentService(db_session, storage_dir=tmp_path)

    response = service.generate_cv(
        DocumentGenerateRequest(
            snapshot_id=snapshot_id,
            language="en",
            formats=["html", "pdf", "docx"],
        )
    )

    assert response.document_type == "cv"
    assert len(response.artifacts) == 3

    artifacts = service.list_snapshot_artifacts(snapshot_id)
    assert len(artifacts.artifacts) == 3

    for artifact in response.artifacts:
        path, mime_type, file_name = service.get_artifact_file(artifact.id)
        assert path.exists()
        assert path.stat().st_size > 0
        assert mime_type == artifact.mime_type
        assert file_name == artifact.file_name


def test_document_service_generates_cover_letter_and_handles_missing_artifacts(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Service should generate cover letter docs and raise for missing artifact IDs."""

    snapshot_id = _create_snapshot(db_session)
    service = DocumentService(db_session, storage_dir=tmp_path)

    response = service.generate_cover_letter(
        DocumentGenerateRequest(
            snapshot_id=snapshot_id,
            language="en",
            formats=["html", "docx"],
        )
    )

    assert response.document_type == "cover_letter"
    assert len(response.artifacts) == 2

    with pytest.raises(DocumentArtifactNotFoundError):
        service.get_artifact("missing-id")

    first_artifact = response.artifacts[0]
    path, _, _ = service.get_artifact_file(first_artifact.id)
    path.unlink()

    with pytest.raises(DocumentFileMissingError):
        service.get_artifact_file(first_artifact.id)


def _create_snapshot(db_session: Session) -> str:
    """Create one tailored snapshot for document tests.

    Args:
        db_session: Active database session.

    Returns:
        Created snapshot identifier.
    """

    profile_service = ProfileService(db_session)
    profile = profile_service.create_profile(
        MasterProfileCreateRequest(
            full_name="Arfan Example",
            email="arfan@example.com",
            phone="+49 123 4567",
            location="Berlin",
            headline="Backend Engineer",
            summary="Python engineer focused on APIs.",
            experiences=[
                {
                    "company": "Example GmbH",
                    "title": "Software Engineer",
                    "description": "Built Python and FastAPI services for 3 years.",
                }
            ],
            educations=[
                {
                    "institution": "TU Example",
                    "degree": "MSc",
                    "field_of_study": "Computer Science",
                }
            ],
            skills=[
                {"skill_name": "Python", "level": "advanced", "category": "programming"},
                {"skill_name": "FastAPI", "level": "advanced", "category": "backend"},
            ],
        )
    )

    job_post_service = JobPostService(db_session)
    job_post = job_post_service.create_job_post(
        JobPostCreateRequest(
            title="Senior Backend Engineer",
            company="Target AG",
            description=(
                "Must have Python and FastAPI experience. "
                "Experience with SQL is required. Nice to have Docker knowledge."
            ),
        )
    )

    job_analysis_service = JobAnalysisService(db_session)
    analysis = job_analysis_service.analyze_job_post(
        job_post_id=job_post.id,
        request=JobAnalysisCreateRequest(use_llm=False),
    )

    tailoring_service = TailoringService(db_session)
    plan = tailoring_service.create_tailoring_plan(
        TailoringPlanCreateRequest(
            job_analysis_id=analysis.id,
            target_language="en",
            max_experiences=1,
            max_skills=2,
            max_educations=1,
        )
    )
    snapshot = tailoring_service.create_snapshot(
        TailoredSnapshotCreateRequest(
            tailoring_plan_id=plan.id,
            rewrites=[],
            use_llm_rewrite=False,
        )
    )

    # Verify master profile remained unchanged by tailoring.
    unchanged_profile = profile_service.get_profile()
    assert unchanged_profile.active_version.version_id == profile.active_version.version_id

    return snapshot.id
