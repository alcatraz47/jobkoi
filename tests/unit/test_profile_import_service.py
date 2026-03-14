"""Unit tests for profile import service orchestration."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.schemas.profile_import import FieldDecisionInput, ProfileImportReviewRequest
from app.services.profile_import_extractors import ExtractedTextResult, WebsitePageResult
from app.services.profile_import_service import ProfileImportService, ProfileImportValidationError


class _FakeCvExtractor:
    """Deterministic fake CV extractor for service tests."""

    def extract_from_file(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        _ = (file_path, file_name, content_type)
        return ExtractedTextResult(
            text=(
                "Arfan Example\n"
                "Backend Engineer\n"
                "arfan@example.com\n"
                "Experience\n"
                "Software Engineer at Example GmbH\n"
                "Skills\n"
                "Python"
            ),
            extractor_name="fake_cv",
        )


class _FakeWebsiteExtractor:
    """Deterministic fake website extractor for service tests."""

    def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
        _ = (url, max_pages)
        return (
            "fake_website",
            [WebsitePageResult(url="https://portfolio.example.dev", text="Arfan Example\narfan@example.com")],
        )


def test_service_apply_requires_review_decisions(db_session: Session, tmp_path) -> None:
    """Service should reject apply when no approved fields exist."""

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    run = service.import_cv(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )

    with pytest.raises(ProfileImportValidationError):
        service.apply_run(run.id)


def test_service_review_and_apply_creates_profile(db_session: Session, tmp_path) -> None:
    """Service should create profile version only after review + apply."""

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    run = service.import_cv(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )

    refreshed = service.get_run(run.id)
    decisions = [
        FieldDecisionInput(field_id=item.id, decision="approve")
        for item in refreshed.fields
    ]
    service.review_run(run.id, ProfileImportReviewRequest(decisions=decisions))

    applied = service.apply_run(run.id)
    assert applied.run.status == "applied"
    assert applied.profile.active_version.version_number == 1
