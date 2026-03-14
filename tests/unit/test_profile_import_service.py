"""Unit tests for profile import service orchestration."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.llm.contracts import ProfileImportExtractionResponse
from app.schemas.profile_import import FieldDecisionInput, ProfileImportReviewRequest
from app.services.profile_import_extractors import ExtractedTextResult, WebsitePageResult
from app.services.profile_import_service import (
    ProfileImportRunNotFoundError,
    ProfileImportService,
    ProfileImportValidationError,
)


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



def test_service_apply_surfaces_validation_error_for_oversized_fields(
    db_session: Session,
    tmp_path,
) -> None:
    """Service should return a domain validation error for oversized reviewed values."""

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
    headline_field = next(item for item in refreshed.fields if item.field_path == "headline")
    decisions = [
        (
            FieldDecisionInput(
                field_id=item.id,
                decision="edit",
                edited_value="A" * 300,
            )
            if item.id == headline_field.id
            else FieldDecisionInput(field_id=item.id, decision="approve")
        )
        for item in refreshed.fields
    ]
    service.review_run(run.id, ProfileImportReviewRequest(decisions=decisions))

    with pytest.raises(ProfileImportValidationError, match="Import apply validation failed"):
        service.apply_run(run.id)


def test_service_delete_run_removes_run_and_source_file(
    db_session: Session,
    tmp_path,
) -> None:
    """Service should delete one import run and its persisted source file."""

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

    assert list((tmp_path / "cv").glob("*"))

    delete_response = service.delete_run(run.id)
    assert delete_response.deleted is True
    assert delete_response.run_id == run.id

    with pytest.raises(ProfileImportRunNotFoundError):
        service.get_run(run.id)

    assert not list((tmp_path / "cv").glob("*"))



class _FakeProfileImportExtractionHelper:
    """Deterministic fake LLM extraction helper for service tests."""

    def __init__(self, response: ProfileImportExtractionResponse) -> None:
        """Initialize fake helper with one fixed response payload.

        Args:
            response: Structured profile extraction response.
        """

        self._response = response

    def extract_profile(
        self,
        *,
        source_type: str,
        source_label: str,
        raw_text: str,
        detected_language: str,
    ) -> ProfileImportExtractionResponse:
        """Return configured response payload.

        Args:
            source_type: Source type.
            source_label: Source label.
            raw_text: Input text.
            detected_language: Input language.

        Returns:
            Structured profile extraction response.
        """

        _ = (source_type, source_label, raw_text, detected_language)
        return self._response


def test_service_cv_import_merges_supported_llm_fields_only(
    db_session: Session,
    tmp_path,
) -> None:
    """Service should merge supported LLM fields and reject unsupported inventions."""

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )
    service._profile_import_llm_enabled = True
    service._profile_import_extraction_helper = _FakeProfileImportExtractionHelper(
        ProfileImportExtractionResponse(
            full_name={"value": "Arfan Example", "source_excerpt": "Arfan Example", "source_locator": "resume.pdf"},
            email={"value": "arfan@example.com", "source_excerpt": "arfan@example.com", "source_locator": "resume.pdf"},
            skills=[
                {"skill_name": "K3s", "source_excerpt": "K3s", "source_locator": "resume.pdf"},
                {"skill_name": "Invented Skill", "source_excerpt": "Invented Skill", "source_locator": "resume.pdf"},
            ],
        )
    )

    run = service.import_cv(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )

    assert run.extractor_name.endswith("+llm")
    values = [field.suggested_value for field in run.fields if field.suggested_value is not None]
    assert "Invented Skill" not in values
