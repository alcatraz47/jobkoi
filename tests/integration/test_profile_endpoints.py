"""Integration tests for profile API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def build_payload(summary: str) -> dict:
    """Build JSON payload for profile requests.

    Args:
        summary: Summary field value.

    Returns:
        JSON-serializable request payload.
    """

    return {
        "full_name": "Arfan Example",
        "email": "arfan@example.com",
        "phone": "+49 123 4567",
        "location": "Berlin",
        "headline": "Python Engineer",
        "summary": summary,
        "experiences": [
            {
                "company": "Example GmbH",
                "title": "Software Engineer",
                "description": "Built APIs.",
            }
        ],
        "educations": [
            {
                "institution": "TU Example",
                "degree": "MSc",
                "field_of_study": "Computer Science",
            }
        ],
        "skills": [{"skill_name": "Python", "level": "advanced", "category": "programming"}],
    }


def test_profile_crud_and_versioning_flow(client: TestClient) -> None:
    """API should support profile CRUD plus version history."""

    create_response = client.post("/api/v1/profile", json=build_payload("Initial summary"))
    assert create_response.status_code == 201
    create_body = create_response.json()
    first_version_id = create_body["active_version"]["version_id"]
    assert create_body["active_version"]["version_number"] == 1

    get_response = client.get("/api/v1/profile")
    assert get_response.status_code == 200
    assert get_response.json()["active_version"]["version_id"] == first_version_id

    update_response = client.put("/api/v1/profile", json=build_payload("Updated summary"))
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["active_version"]["version_number"] == 2
    assert update_body["active_version"]["summary"] == "Updated summary"

    versions_response = client.get("/api/v1/profile/versions")
    assert versions_response.status_code == 200
    versions_body = versions_response.json()
    assert len(versions_body["versions"]) == 2

    first_version_response = client.get(f"/api/v1/profile/versions/{first_version_id}")
    assert first_version_response.status_code == 200
    assert first_version_response.json()["summary"] == "Initial summary"

    delete_response = client.delete("/api/v1/profile")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    missing_response = client.get("/api/v1/profile")
    assert missing_response.status_code == 404


def test_profile_create_conflict(client: TestClient) -> None:
    """API should return conflict when creating profile twice."""

    first = client.post("/api/v1/profile", json=build_payload("Summary"))
    assert first.status_code == 201

    second = client.post("/api/v1/profile", json=build_payload("Summary 2"))
    assert second.status_code == 409
