"""Integration tests for job submission and job analysis endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_job_submission_and_analysis_flow(client: TestClient) -> None:
    """API should ingest a job post and return a structured analysis."""

    job_payload = {
        "title": "Backend Engineer",
        "company": "Example GmbH",
        "description": (
            "Must have Python and SQL experience. "
            "Nice to have Docker knowledge. "
            "Strong communication skills required."
        ),
    }

    create_job_response = client.post("/api/v1/job-posts", json=job_payload)
    assert create_job_response.status_code == 201
    create_job_body = create_job_response.json()
    job_post_id = create_job_body["id"]

    assert create_job_body["title"] == "Backend Engineer"
    assert create_job_body["detected_language"] == "en"

    analyze_response = client.post(
        f"/api/v1/job-posts/{job_post_id}/analyses",
        json={"use_llm": False},
    )
    assert analyze_response.status_code == 201
    analysis_body = analyze_response.json()
    analysis_id = analysis_body["id"]

    assert analysis_body["job_post_id"] == job_post_id
    assert analysis_body["normalized_title"] == "Backend Engineer"
    assert len(analysis_body["requirements"]) >= 2
    assert any(item["is_must_have"] for item in analysis_body["requirements"])
    assert any(item["is_nice_to_have"] for item in analysis_body["requirements"])

    latest_response = client.get(f"/api/v1/job-posts/{job_post_id}/analyses/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == analysis_id

    one_response = client.get(f"/api/v1/job-analyses/{analysis_id}")
    assert one_response.status_code == 200
    assert one_response.json()["id"] == analysis_id


def test_analysis_endpoints_return_not_found_for_missing_job(client: TestClient) -> None:
    """Analysis endpoints should return not found for unknown job posts."""

    analyze_response = client.post("/api/v1/job-posts/missing/analyses", json={"use_llm": False})
    assert analyze_response.status_code == 404

    latest_response = client.get("/api/v1/job-posts/missing/analyses/latest")
    assert latest_response.status_code == 404
