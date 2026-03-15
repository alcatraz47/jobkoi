"""Unit tests for profile import service orchestration."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.llm.contracts import (
    ProfileImportAuditResponse,
    ProfileImportExtractionResponse,
)
from app.schemas.profile_import import FieldDecisionInput, ProfileImportReviewRequest, WebsiteImportRequest
from app.services.profile_import_extractors import ExtractedTextResult, ProfileImportExtractionError, WebsitePageResult
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

    class _LongWebsiteExtractor:
        """Deterministic website extractor yielding long text for LLM path tests."""

        def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
            _ = (url, max_pages)
            return (
                "fake_website",
                [
                    WebsitePageResult(
                        url="https://portfolio.example.dev",
                        text=(
                            "Arfan Example builds backend systems with Python and FastAPI for logistics workflows. "
                            "He designs data pipelines and deployment automation across production environments."
                        ),
                    )
                ],
            )

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_LongWebsiteExtractor(),
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

    def __init__(
        self,
        response: ProfileImportExtractionResponse,
        *,
        audit_response: ProfileImportAuditResponse | None = None,
    ) -> None:
        """Initialize fake helper with fixed extraction and optional audit payload.

        Args:
            response: Structured profile extraction response.
            audit_response: Optional structured profile audit response.
        """

        self._response = response
        self._audit_response = audit_response or ProfileImportAuditResponse()

    def extract_profile(
        self,
        *,
        source_type: str,
        source_label: str,
        raw_text: str,
        detected_language: str,
    ) -> ProfileImportExtractionResponse:
        """Return configured extraction payload."""

        _ = (source_type, source_label, raw_text, detected_language)
        return self._response

    def audit_profile(
        self,
        *,
        source_type: str,
        source_label: str,
        raw_text: str,
        detected_language: str,
        candidate_profile_json: str,
    ) -> ProfileImportAuditResponse:
        """Return configured supervisor audit payload."""

        _ = (source_type, source_label, raw_text, detected_language, candidate_profile_json)
        return self._audit_response


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


class _FailingCvExtractor:
    """Deterministic failing CV extractor for queue failure tests."""

    def extract_from_file(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        """Raise one extraction error for test assertions."""

        _ = (file_path, file_name, content_type)
        raise ProfileImportExtractionError("failed to parse cv")


def test_service_enqueue_and_process_cv_import(db_session: Session, tmp_path) -> None:
    """Queued CV import should transition from queued to extracted after processing."""

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    queued = service.enqueue_cv_import(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )
    assert queued.status == "queued"
    assert queued.fields == []

    service.process_queued_cv_run(queued.id)

    processed = service.get_run(queued.id)
    assert processed.status == "extracted"
    assert processed.fields


def test_service_enqueue_cv_import_marks_failed_on_extraction_error(
    db_session: Session,
    tmp_path,
) -> None:
    """Queued CV import should be marked failed when extractor raises."""

    service = ProfileImportService(
        db_session,
        cv_extractor=_FailingCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    queued = service.enqueue_cv_import(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )

    service.process_queued_cv_run(queued.id)

    failed = service.get_run(queued.id)
    assert failed.status == "failed"



def test_service_website_import_merges_supported_llm_fields_only(
    db_session: Session,
    tmp_path,
) -> None:
    """Website import should use LLM merge path with source-supported fields only."""

    class _LongWebsiteExtractor:
        """Deterministic website extractor yielding long text for LLM path tests."""

        def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
            _ = (url, max_pages)
            return (
                "fake_website",
                [
                    WebsitePageResult(
                        url="https://portfolio.example.dev",
                        text=(
                            "Arfan Example builds backend systems with Python and FastAPI for logistics workflows. "
                            "He designs data pipelines and deployment automation across production environments."
                        ),
                    )
                ],
            )

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_LongWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )
    service._profile_import_llm_enabled = True
    service._profile_import_extraction_helper = _FakeProfileImportExtractionHelper(
        ProfileImportExtractionResponse(
            full_name={
                "value": "Arfan Example",
                "source_excerpt": "Arfan Example",
                "source_locator": "https://portfolio.example.dev",
            },
            skills=[
                {
                    "skill_name": "Python",
                    "source_excerpt": "Python",
                    "source_locator": "https://portfolio.example.dev",
                },
                {
                    "skill_name": "Invented Skill",
                    "source_excerpt": "Invented Skill",
                    "source_locator": "https://portfolio.example.dev",
                },
            ],
        )
    )

    run = service.import_website(
        WebsiteImportRequest(url="https://portfolio.example.dev", max_pages=2)
    )

    assert run.extractor_name.endswith("+llm")
    values = [field.suggested_value for field in run.fields if field.suggested_value is not None]
    assert "Invented Skill" not in values



def test_service_enqueue_and_process_website_import(db_session: Session, tmp_path) -> None:
    """Queued website import should transition from queued to extracted."""

    class _LongWebsiteExtractor:
        """Deterministic website extractor for queue processing tests."""

        def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
            _ = (url, max_pages)
            return (
                "fake_website",
                [
                    WebsitePageResult(
                        url=url,
                        text=(
                            "Arfan Example builds backend systems with Python and FastAPI for logistics workflows. "
                            "He designs data pipelines and deployment automation across production environments."
                        ),
                    )
                ],
            )

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_LongWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    queued = service.enqueue_website_import(
        WebsiteImportRequest(url="https://portfolio.example.dev", max_pages=2)
    )
    assert queued.status == "queued"
    assert queued.fields == []

    service.process_queued_website_run(queued.id)

    processed = service.get_run(queued.id)
    assert processed.status == "extracted"
    assert processed.fields


def test_service_supervisor_reassigns_education_like_location_to_education(
    db_session: Session,
    tmp_path,
) -> None:
    """Supervisor should move education-like scalar text out of location."""

    class _EducationLikeCvExtractor:
        """Deterministic CV extractor with education text in source."""

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
                    "Arfan Example\\n"
                    "Master of Data Science, Carl von Ossietzky University Oldenburg\\n"
                    "arfan@example.com\\n"
                ),
                extractor_name="fake_cv",
            )

    service = ProfileImportService(
        db_session,
        cv_extractor=_EducationLikeCvExtractor(),
        website_extractor=_FakeWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )
    service._profile_import_llm_enabled = True
    service._profile_import_llm_supervisor_enabled = True
    service._profile_import_extraction_helper = _FakeProfileImportExtractionHelper(
        ProfileImportExtractionResponse(
            full_name={"value": "Arfan Example", "source_excerpt": "Arfan Example", "source_locator": "resume.pdf"},
            email={"value": "arfan@example.com", "source_excerpt": "arfan@example.com", "source_locator": "resume.pdf"},
            location={
                "value": "Master of Data Science, Carl von Ossietzky University Oldenburg",
                "source_excerpt": "Master of Data Science, Carl von Ossietzky University Oldenburg",
                "source_locator": "resume.pdf",
            },
        ),
        audit_response=ProfileImportAuditResponse(
            scalar_suggestions=[
                {
                    "field_name": "location",
                    "action": "move_to_education",
                    "suggested_value": "Master of Data Science, Carl von Ossietzky University Oldenburg",
                }
            ]
        ),
    )

    run = service.import_cv(
        file_name="resume.pdf",
        content_type="application/pdf",
        file_bytes=b"pdf-bytes",
    )

    field_values = {item.field_path: item.suggested_value for item in run.fields}
    assert field_values.get("location") != "Master of Data Science, Carl von Ossietzky University Oldenburg"
    assert any(
        str(item.suggested_value).startswith("Master of Data Science")
        for item in run.fields
        if item.field_path.endswith(".degree")
    )


def test_service_website_import_keeps_multiple_experience_entries_for_review(
    db_session: Session,
    tmp_path,
) -> None:
    """Website import should preserve separate experience entries and blank-title review rows."""

    class _StructuredWebsiteExtractor:
        """Deterministic website extractor with multi-entry experience page."""

        def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
            _ = (url, max_pages)
            return (
                "fake_website",
                [
                    WebsitePageResult(
                        url="https://portfolio.example.dev",
                        text=(
                            "Md Mahmudul Haque\n"
                            "AI Engineer • Computer Vision • NLP • LLMs/VLMs\n"
                            "arfan@example.com\n"
                        ),
                    ),
                    WebsitePageResult(
                        url="https://portfolio.example.dev/experience/",
                        text=(
                            "Experience\n"
                            "HT Ventures (January 2025-Present)\n"
                            "Role: AI Engineer (Remote)\n"
                            "- Built customer support copilots.\n"
                            "Fraunhofer IML (May 2025-Present)\n"
                            "- Built railway computer vision systems.\n"
                            "Henkel (Apr 2024-Apr 2025)\n"
                            "- Built sustainability NLP workflows.\n"
                        ),
                    ),
                ],
            )

    service = ProfileImportService(
        db_session,
        cv_extractor=_FakeCvExtractor(),
        website_extractor=_StructuredWebsiteExtractor(),
        import_storage_dir=tmp_path,
    )

    run = service.import_website(
        WebsiteImportRequest(url="https://portfolio.example.dev", max_pages=2)
    )

    field_values = {(item.field_path, item.suggested_value) for item in run.fields}
    assert ("experiences[0].company", "HT Ventures") in field_values
    assert ("experiences[0].title", "AI Engineer (Remote)") in field_values
    assert ("experiences[1].company", "Fraunhofer IML") in field_values
    assert ("experiences[1].title", "") in field_values
    assert ("experiences[2].company", "Henkel") in field_values
    assert ("experiences[2].title", "") in field_values
