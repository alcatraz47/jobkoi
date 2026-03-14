"""Integration tests for tailoring plan and snapshot endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def build_profile_payload() -> dict:
    """Build profile creation payload for tailoring integration tests.

    Returns:
        JSON-serializable profile payload.
    """

    return {
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
            },
            {
                "company": "Another GmbH",
                "title": "Developer",
                "description": "Worked on frontend pages.",
            },
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
            {"skill_name": "React", "level": "intermediate", "category": "frontend"},
        ],
    }


def build_job_payload() -> dict:
    """Build job post payload for tailoring integration tests.

    Returns:
        JSON-serializable job payload.
    """

    return {
        "title": "Senior Backend Engineer",
        "company": "Target AG",
        "description": (
            "Must have Python and FastAPI experience. "
            "Experience with SQL is required. "
            "Nice to have Docker knowledge."
        ),
    }


def test_tailoring_plan_and_snapshot_flow(client: TestClient) -> None:
    """API should create deterministic tailoring plan and immutable snapshot."""

    profile_response = client.post("/api/v1/profile", json=build_profile_payload())
    assert profile_response.status_code == 201
    original_summary = profile_response.json()["active_version"]["summary"]

    job_response = client.post("/api/v1/job-posts", json=build_job_payload())
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
    plan_body = plan_response.json()
    plan_id = plan_body["id"]

    assert plan_body["selected_item_count"] >= 2
    assert any(item["is_selected"] for item in plan_body["items"])
    assert any(item["fact_key"].startswith("experience:") and item["is_selected"] for item in plan_body["items"])

    get_plan_response = client.get(f"/api/v1/tailoring/plans/{plan_id}")
    assert get_plan_response.status_code == 200
    assert get_plan_response.json()["id"] == plan_id

    snapshot_response = client.post(
        "/api/v1/tailoring/snapshots",
        json={
            "tailoring_plan_id": plan_id,
            "rewrites": [],
            "use_llm_rewrite": False,
        },
    )
    assert snapshot_response.status_code == 201
    snapshot_body = snapshot_response.json()
    snapshot_id = snapshot_body["id"]

    assert snapshot_body["tailoring_plan_id"] == plan_id
    assert len(snapshot_body["experiences"]) == 1
    assert len(snapshot_body["skills"]) >= 1

    get_snapshot_response = client.get(f"/api/v1/tailoring/snapshots/{snapshot_id}")
    assert get_snapshot_response.status_code == 200
    assert get_snapshot_response.json()["id"] == snapshot_id

    profile_after_tailoring = client.get("/api/v1/profile")
    assert profile_after_tailoring.status_code == 200
    assert profile_after_tailoring.json()["active_version"]["summary"] == original_summary


def test_tailoring_snapshot_rejects_invented_claims(client: TestClient) -> None:
    """Snapshot endpoint should reject rewrites with invented numeric claims."""

    profile_response = client.post("/api/v1/profile", json=build_profile_payload())
    assert profile_response.status_code == 201

    job_response = client.post("/api/v1/job-posts", json=build_job_payload())
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
    plan_body = plan_response.json()

    selected_experience = next(
        item for item in plan_body["items"] if item["fact_key"].startswith("experience:") and item["is_selected"]
    )

    snapshot_response = client.post(
        "/api/v1/tailoring/snapshots",
        json={
            "tailoring_plan_id": plan_body["id"],
            "rewrites": [
                {
                    "fact_key": selected_experience["fact_key"],
                    "rewritten_text": "Built Python and FastAPI services for 8 years.",
                }
            ],
            "use_llm_rewrite": False,
        },
    )
    assert snapshot_response.status_code == 422
