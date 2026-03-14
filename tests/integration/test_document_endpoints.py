"""Integration tests for document generation and retrieval endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_document_generation_and_download_flow(client: TestClient) -> None:
    """API should generate document artifacts and support retrieval/download."""

    snapshot_id = _create_snapshot_graph(client)

    generate_response = client.post(
        "/api/v1/documents/cv",
        json={
            "snapshot_id": snapshot_id,
            "language": "en",
            "formats": ["html", "pdf"],
        },
    )
    assert generate_response.status_code == 201
    generate_body = generate_response.json()
    assert generate_body["document_type"] == "cv"
    assert len(generate_body["artifacts"]) == 2

    artifact_id = generate_body["artifacts"][0]["id"]

    metadata_response = client.get(f"/api/v1/documents/{artifact_id}")
    assert metadata_response.status_code == 200

    list_response = client.get(f"/api/v1/documents/snapshots/{snapshot_id}")
    assert list_response.status_code == 200
    assert len(list_response.json()["artifacts"]) == 2

    download_response = client.get(f"/api/v1/documents/{artifact_id}/download")
    assert download_response.status_code == 200
    assert len(download_response.content) > 0


def _create_snapshot_graph(client: TestClient) -> str:
    """Create one job-tailoring snapshot graph for document integration tests.

    Args:
        client: FastAPI test client.

    Returns:
        Tailored snapshot identifier.
    """

    profile_response = client.post(
        "/api/v1/profile",
        json={
            "full_name": "Arfan Example",
            "email": "arfan@example.com",
            "phone": "+49 123 4567",
            "location": "Berlin",
            "headline": "Backend Engineer",
            "summary": "Python engineer focused on APIs.",
            "experiences": [
                {
                    "company": "Example GmbH",
                    "title": "Software Engineer",
                    "description": "Built Python and FastAPI services for 3 years.",
                }
            ],
            "educations": [
                {
                    "institution": "TU Example",
                    "degree": "MSc",
                    "field_of_study": "Computer Science",
                }
            ],
            "skills": [
                {"skill_name": "Python", "level": "advanced", "category": "programming"},
                {"skill_name": "FastAPI", "level": "advanced", "category": "backend"},
            ],
        },
    )
    assert profile_response.status_code == 201

    job_response = client.post(
        "/api/v1/job-posts",
        json={
            "title": "Senior Backend Engineer",
            "company": "Target AG",
            "description": "Must have Python and FastAPI experience. Nice to have Docker.",
        },
    )
    assert job_response.status_code == 201
    job_post_id = job_response.json()["id"]

    analysis_response = client.post(f"/api/v1/job-posts/{job_post_id}/analyses", json={"use_llm": False})
    assert analysis_response.status_code == 201
    analysis_id = analysis_response.json()["id"]

    plan_response = client.post(
        "/api/v1/tailoring/plans",
        json={
            "job_analysis_id": analysis_id,
            "target_language": "en",
            "max_experiences": 1,
            "max_skills": 2,
            "max_educations": 1,
        },
    )
    assert plan_response.status_code == 201
    plan_id = plan_response.json()["id"]

    snapshot_response = client.post(
        "/api/v1/tailoring/snapshots",
        json={
            "tailoring_plan_id": plan_id,
            "rewrites": [],
            "use_llm_rewrite": False,
        },
    )
    assert snapshot_response.status_code == 201
    return snapshot_response.json()["id"]
