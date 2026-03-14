"""Unit tests for application package service behavior."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.schemas.application_package import ApplicationPackageCreateRequest
from app.schemas.document import DocumentGenerateRequest
from app.schemas.job import JobAnalysisCreateRequest, JobPostCreateRequest
from app.schemas.profile import MasterProfileCreateRequest
from app.schemas.tailoring import TailoredSnapshotCreateRequest, TailoringPlanCreateRequest
from app.services.application_package_service import (
    ApplicationPackageDependencyError,
    ApplicationPackageNotFoundError,
    ApplicationPackageService,
    ApplicationPackageValidationError,
)
from app.services.document_service import DocumentService
from app.services.job_analysis_service import JobAnalysisService
from app.services.job_post_service import JobPostService
from app.services.profile_service import ProfileNotFoundError, ProfileService
from app.services.tailoring_service import TailoringService


@dataclass(frozen=True)
class SnapshotGraph:
    """Identifiers for one job-to-snapshot tailoring graph."""

    job_post_id: str
    analysis_id: str
    plan_id: str
    snapshot_id: str


def test_application_package_service_creates_and_retrieves_package(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Service should persist package links and retrieve package records."""

    graph = _create_snapshot_graph(db_session, title="Senior Backend Engineer")
    document_service = DocumentService(db_session, storage_dir=tmp_path)
    generated = document_service.generate_cv(
        DocumentGenerateRequest(
            snapshot_id=graph.snapshot_id,
            language="en",
            formats=["html", "pdf"],
        )
    )

    package_service = ApplicationPackageService(db_session)
    package = package_service.create_package(
        ApplicationPackageCreateRequest(
            job_post_id=graph.job_post_id,
            job_analysis_id=graph.analysis_id,
            tailoring_plan_id=graph.plan_id,
            profile_snapshot_id=graph.snapshot_id,
            document_artifact_ids=[artifact.id for artifact in generated.artifacts],
        )
    )

    assert package.profile_snapshot_id == graph.snapshot_id
    assert len(package.documents) == 2
    assert len(package.events) >= 2

    loaded = package_service.get_package(package.id)
    assert loaded.id == package.id
    assert {item.artifact_id for item in loaded.documents} == {item.id for item in generated.artifacts}

    listing = package_service.list_packages()
    assert listing.packages[0].id == package.id


def test_application_package_service_rejects_artifact_from_other_snapshot(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Service should reject package creation when artifacts target a different snapshot."""

    graph = _create_snapshot_graph(db_session, title="Senior Backend Engineer")
    other_graph = _create_snapshot_graph(db_session, title="Platform Engineer")

    document_service = DocumentService(db_session, storage_dir=tmp_path)
    good_artifact = document_service.generate_cv(
        DocumentGenerateRequest(
            snapshot_id=graph.snapshot_id,
            language="en",
            formats=["html"],
        )
    ).artifacts[0]
    bad_artifact = document_service.generate_cv(
        DocumentGenerateRequest(
            snapshot_id=other_graph.snapshot_id,
            language="en",
            formats=["pdf"],
        )
    ).artifacts[0]

    package_service = ApplicationPackageService(db_session)
    with pytest.raises(ApplicationPackageValidationError):
        package_service.create_package(
            ApplicationPackageCreateRequest(
                job_post_id=graph.job_post_id,
                job_analysis_id=graph.analysis_id,
                tailoring_plan_id=graph.plan_id,
                profile_snapshot_id=graph.snapshot_id,
                document_artifact_ids=[good_artifact.id, bad_artifact.id],
            )
        )

    with pytest.raises(ApplicationPackageNotFoundError):
        package_service.get_package("missing-package")

def test_application_package_service_deduplicates_duplicate_artifact_ids(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Service should keep one linked document row for duplicate artifact IDs."""

    graph = _create_snapshot_graph(db_session, title="Senior Backend Engineer")
    document_service = DocumentService(db_session, storage_dir=tmp_path)
    artifact = document_service.generate_cv(
        DocumentGenerateRequest(
            snapshot_id=graph.snapshot_id,
            language="en",
            formats=["html"],
        )
    ).artifacts[0]

    package_service = ApplicationPackageService(db_session)
    package = package_service.create_package(
        ApplicationPackageCreateRequest(
            job_post_id=graph.job_post_id,
            job_analysis_id=graph.analysis_id,
            tailoring_plan_id=graph.plan_id,
            profile_snapshot_id=graph.snapshot_id,
            document_artifact_ids=[artifact.id, artifact.id],
        )
    )

    assert len(package.documents) == 1
    assert package.documents[0].artifact_id == artifact.id


def test_application_package_service_reports_missing_dependencies(db_session: Session) -> None:
    """Service should raise dependency error when linked entities do not exist."""

    package_service = ApplicationPackageService(db_session)
    with pytest.raises(ApplicationPackageDependencyError):
        package_service.create_package(
            ApplicationPackageCreateRequest(
                job_post_id="missing-job",
                job_analysis_id="missing-analysis",
                tailoring_plan_id="missing-plan",
                profile_snapshot_id="missing-snapshot",
                document_artifact_ids=[],
            )
        )


def _create_snapshot_graph(db_session: Session, *, title: str) -> SnapshotGraph:
    """Create one deterministic job-to-snapshot graph.

    Args:
        db_session: Active database session.
        title: Job title for the created job post.

    Returns:
        Identifiers for the created graph.
    """

    _ensure_profile_exists(db_session)

    job_post_service = JobPostService(db_session)
    job_post = job_post_service.create_job_post(
        JobPostCreateRequest(
            title=title,
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
    return SnapshotGraph(
        job_post_id=job_post.id,
        analysis_id=analysis.id,
        plan_id=plan.id,
        snapshot_id=snapshot.id,
    )


def _ensure_profile_exists(db_session: Session) -> None:
    """Create the singleton master profile once for tests.

    Args:
        db_session: Active database session.
    """

    profile_service = ProfileService(db_session)
    try:
        profile_service.get_profile()
        return
    except ProfileNotFoundError:
        pass

    profile_service.create_profile(
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
