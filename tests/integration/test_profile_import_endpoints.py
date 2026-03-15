"""Integration tests for profile import API routes."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.services.profile_import_service as profile_import_service_module
from app.services.profile_import_extractors import ExtractedTextResult, WebsitePageResult


def _profile_payload(email: str) -> dict[str, object]:
    """Return a baseline profile payload for tests."""

    return {
        "full_name": "Arfan Example",
        "email": email,
        "phone": "+49 123 4567",
        "location": "Berlin",
        "headline": "Backend Engineer",
        "summary": "Builds backend systems.",
        "experiences": [
            {
                "company": "Example GmbH",
                "title": "Software Engineer",
                "description": "Built APIs.",
            }
        ],
        "educations": [
            {
                "institution": "TU Berlin",
                "degree": "MSc",
                "field_of_study": "Computer Science",
            }
        ],
        "skills": [
            {
                "skill_name": "Python",
                "level": "advanced",
                "category": "backend",
            }
        ],
    }


def test_cv_import_requires_review_before_apply(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    """CV import should not mutate master profile before explicit review and apply."""

    monkeypatch.setattr(
        profile_import_service_module,
        "get_settings",
        lambda: SimpleNamespace(import_storage_dir=str(tmp_path / "imports")),
    )

    def fake_extract(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        _ = (self, file_path, file_name, content_type)
        return ExtractedTextResult(
            text=(
                "Arfan Example\n"
                "Backend Engineer\n"
                "arfan@example.com\n"
                "+49 123 4567\n"
                "Experience\n"
                "Software Engineer at Example GmbH\n"
                "Skills\n"
                "Python, FastAPI"
            ),
            extractor_name="fake_cv",
        )

    monkeypatch.setattr(
        "app.services.profile_import_extractors.CvImportExtractor.extract_from_file",
        fake_extract,
    )

    import_response = client.post(
        "/api/v1/profile-imports/cv",
        files={
            "file": (
                "resume.pdf",
                b"fake-pdf-bytes",
                "application/pdf",
            )
        },
    )
    assert import_response.status_code == 201

    run = import_response.json()
    assert run["status"] == "extracted"
    run_id = run["id"]
    assert run["fields"]

    # Import run creation alone must not create or mutate master profile.
    pre_apply_profile = client.get("/api/v1/profile")
    assert pre_apply_profile.status_code == 404

    decisions = [{"field_id": item["id"], "decision": "approve"} for item in run["fields"]]
    review_response = client.post(
        f"/api/v1/profile-imports/{run_id}/review",
        json={"decisions": decisions, "conflict_resolutions": []},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "reviewed"

    apply_response = client.post(f"/api/v1/profile-imports/{run_id}/apply")
    assert apply_response.status_code == 200

    body = apply_response.json()
    assert body["run"]["status"] == "applied"
    assert body["profile"]["active_version"]["version_number"] == 1
    assert body["run"]["applied_facts"]


def test_website_import_blocks_apply_when_conflicts_are_unresolved(
    client: TestClient,
    monkeypatch,
) -> None:
    """Website import apply should fail until detected conflicts are explicitly resolved."""

    create_profile = client.post("/api/v1/profile", json=_profile_payload(email="old@example.com"))
    assert create_profile.status_code == 201

    def fake_website_extract(
        self,
        *,
        url: str,
        max_pages: int,
    ) -> tuple[str, list[WebsitePageResult]]:
        _ = (self, url, max_pages)
        return (
            "fake_website",
            [
                WebsitePageResult(
                    url="https://portfolio.example.dev",
                    text=(
                        "Arfan Example\n"
                        "Backend Engineer\n"
                        "new@example.com\n"
                        "Experience\n"
                        "Software Engineer at Example GmbH\n"
                        "Skills\n"
                        "Python, Docker"
                    ),
                )
            ],
        )

    monkeypatch.setattr(
        "app.services.profile_import_extractors.WebsiteImportExtractor.extract_from_url",
        fake_website_extract,
    )

    import_response = client.post(
        "/api/v1/profile-imports/website",
        json={"url": "https://portfolio.example.dev", "max_pages": 2},
    )
    assert import_response.status_code == 201

    run = import_response.json()
    run_id = run["id"]
    assert run["conflicts"]

    decisions = [{"field_id": item["id"], "decision": "approve"} for item in run["fields"]]
    review_response = client.post(
        f"/api/v1/profile-imports/{run_id}/review",
        json={"decisions": decisions, "conflict_resolutions": []},
    )
    assert review_response.status_code == 200

    blocked_apply = client.post(f"/api/v1/profile-imports/{run_id}/apply")
    assert blocked_apply.status_code == 422
    assert "Resolve all detected conflicts" in blocked_apply.json()["detail"]

    resolutions = [
        {
            "conflict_id": item["id"],
            "resolution_status": "keep_existing",
            "resolution_note": "Prefer existing verified master profile data.",
        }
        for item in run["conflicts"]
    ]
    resolve_response = client.post(
        f"/api/v1/profile-imports/{run_id}/review",
        json={"decisions": [], "conflict_resolutions": resolutions},
    )
    assert resolve_response.status_code == 200

    apply_response = client.post(f"/api/v1/profile-imports/{run_id}/apply")
    assert apply_response.status_code == 200
    assert apply_response.json()["profile"]["active_version"]["version_number"] == 2


def test_cv_import_apply_returns_422_for_oversized_experience_fields(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    """API should return 422 when reviewed values violate profile schema constraints."""

    monkeypatch.setattr(
        profile_import_service_module,
        "get_settings",
        lambda: SimpleNamespace(import_storage_dir=str(tmp_path / "imports")),
    )

    def fake_extract(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        _ = (self, file_path, file_name, content_type)
        return ExtractedTextResult(
            text=(
                "Arfan Example\n"
                "Backend Engineer\n"
                "arfan@example.com\n"
                "Experience\n"
                "Software Engineer at Example GmbH\n"
                "Skills\n"
                "Python, FastAPI"
            ),
            extractor_name="fake_cv",
        )

    monkeypatch.setattr(
        "app.services.profile_import_extractors.CvImportExtractor.extract_from_file",
        fake_extract,
    )

    import_response = client.post(
        "/api/v1/profile-imports/cv",
        files={
            "file": (
                "resume.pdf",
                b"fake-pdf-bytes",
                "application/pdf",
            )
        },
    )
    assert import_response.status_code == 201

    run = import_response.json()
    run_id = run["id"]
    headline_field = next(item for item in run["fields"] if item["field_path"] == "headline")
    decisions = [
        (
            {"field_id": item["id"], "decision": "edit", "edited_value": "A" * 300}
            if item["id"] == headline_field["id"]
            else {"field_id": item["id"], "decision": "approve"}
        )
        for item in run["fields"]
    ]
    review_response = client.post(
        f"/api/v1/profile-imports/{run_id}/review",
        json={"decisions": decisions, "conflict_resolutions": []},
    )
    assert review_response.status_code == 200

    apply_response = client.post(f"/api/v1/profile-imports/{run_id}/apply")
    assert apply_response.status_code == 422
    assert "Import apply validation failed" in apply_response.json()["detail"]


def test_profile_import_run_delete_endpoint_removes_run(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    """Delete endpoint should remove one import run and make it inaccessible."""

    monkeypatch.setattr(
        profile_import_service_module,
        "get_settings",
        lambda: SimpleNamespace(import_storage_dir=str(tmp_path / "imports")),
    )

    def fake_extract(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        _ = (self, file_path, file_name, content_type)
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

    monkeypatch.setattr(
        "app.services.profile_import_extractors.CvImportExtractor.extract_from_file",
        fake_extract,
    )

    import_response = client.post(
        "/api/v1/profile-imports/cv",
        files={"file": ("resume.pdf", b"fake-pdf-bytes", "application/pdf")},
    )
    assert import_response.status_code == 201

    run_id = import_response.json()["id"]
    delete_response = client.delete(f"/api/v1/profile-imports/{run_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True, "run_id": run_id}

    get_response = client.get(f"/api/v1/profile-imports/{run_id}")
    assert get_response.status_code == 404

    assert not list((tmp_path / "imports" / "cv").glob("*"))




def test_cv_import_async_endpoint_queues_and_processes_run(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    """Async CV endpoint should return queued run and eventually produce extraction output."""

    monkeypatch.setattr(
        profile_import_service_module,
        "get_settings",
        lambda: SimpleNamespace(import_storage_dir=str(tmp_path / "imports")),
    )

    def fake_extract(
        self,
        *,
        file_path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        _ = (self, file_path, file_name, content_type)
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

    monkeypatch.setattr(
        "app.services.profile_import_extractors.CvImportExtractor.extract_from_file",
        fake_extract,
    )

    import_response = client.post(
        "/api/v1/profile-imports/cv/async",
        files={"file": ("resume.pdf", b"fake-pdf-bytes", "application/pdf")},
    )
    assert import_response.status_code == 202

    queued = import_response.json()
    run_id = queued["id"]
    assert queued["status"] == "queued"

    get_response = client.get(f"/api/v1/profile-imports/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] in {"queued", "running", "extracted"}
