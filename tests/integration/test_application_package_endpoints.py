"""Integration tests for application package endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_application_package_create_list_get_flow(client: TestClient) -> None:
    """API should create, list, and retrieve reproducible application packages."""

    graph = _create_snapshot_graph(client, title="Senior Backend Engineer")
    artifacts = _generate_cv_artifacts(client, graph["snapshot_id"])

    create_response = client.post(
        "/api/v1/application-packages",
        json={
            "job_post_id": graph["job_post_id"],
            "job_analysis_id": graph["analysis_id"],
            "tailoring_plan_id": graph["plan_id"],
            "profile_snapshot_id": graph["snapshot_id"],
            "document_artifact_ids": [item["id"] for item in artifacts],
        },
    )
    assert create_response.status_code == 201
    package_body = create_response.json()
    package_id = package_body["id"]

    assert package_body["profile_snapshot_id"] == graph["snapshot_id"]
    assert len(package_body["documents"]) == len(artifacts)
    assert len(package_body["events"]) >= 2

    list_response = client.get("/api/v1/application-packages")
    assert list_response.status_code == 200
    listed = list_response.json()["packages"]
    assert any(item["id"] == package_id for item in listed)

    get_response = client.get(f"/api/v1/application-packages/{package_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == package_id


def test_application_package_endpoint_rejects_mismatched_artifact(client: TestClient) -> None:
    """API should reject package creation when a document belongs to a different snapshot."""

    first_graph = _create_snapshot_graph(client, title="Senior Backend Engineer")
    second_graph = _create_snapshot_graph(client, title="Platform Engineer")

    first_artifact = _generate_cv_artifacts(client, first_graph["snapshot_id"])[0]
    second_artifact = _generate_cv_artifacts(client, second_graph["snapshot_id"])[0]

    create_response = client.post(
        "/api/v1/application-packages",
        json={
            "job_post_id": first_graph["job_post_id"],
            "job_analysis_id": first_graph["analysis_id"],
            "tailoring_plan_id": first_graph["plan_id"],
            "profile_snapshot_id": first_graph["snapshot_id"],
            "document_artifact_ids": [first_artifact["id"], second_artifact["id"]],
        },
    )
    assert create_response.status_code == 422

def test_application_package_get_missing_returns_404(client: TestClient) -> None:
    """API should return 404 when requesting an unknown package identifier."""

    response = client.get("/api/v1/application-packages/missing-package")
    assert response.status_code == 404


def test_application_package_create_returns_404_for_missing_dependencies(client: TestClient) -> None:
    """API should return 404 when create request references missing dependencies."""

    response = client.post(
        "/api/v1/application-packages",
        json={
            "job_post_id": "missing-job",
            "job_analysis_id": "missing-analysis",
            "tailoring_plan_id": "missing-plan",
            "profile_snapshot_id": "missing-snapshot",
            "document_artifact_ids": [],
        },
    )
    assert response.status_code == 404


def _create_snapshot_graph(client: TestClient, *, title: str) -> dict[str, str]:
    """Create one end-to-end tailoring graph for integration tests.

    Args:
        client: FastAPI test client.
        title: Job title used for job post creation.

    Returns:
        Dictionary containing linked entity identifiers.
    """

    _ensure_profile(client)

    job_response = client.post(
        "/api/v1/job-posts",
        json={
            "title": title,
            "company": "Target AG",
            "description": (
                "Must have Python and FastAPI experience. "
                "Experience with SQL is required. Nice to have Docker knowledge."
            ),
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
    snapshot_id = snapshot_response.json()["id"]

    return {
        "job_post_id": job_post_id,
        "analysis_id": analysis_id,
        "plan_id": plan_id,
        "snapshot_id": snapshot_id,
    }


def _generate_cv_artifacts(client: TestClient, snapshot_id: str) -> list[dict[str, object]]:
    """Generate CV artifacts for one snapshot.

    Args:
        client: FastAPI test client.
        snapshot_id: Snapshot identifier.

    Returns:
        List of generated artifact payloads.
    """

    response = client.post(
        "/api/v1/documents/cv",
        json={
            "snapshot_id": snapshot_id,
            "language": "en",
            "formats": ["html", "pdf"],
        },
    )
    assert response.status_code == 201
    artifacts = response.json()["artifacts"]
    assert len(artifacts) == 2
    return artifacts


def _ensure_profile(client: TestClient) -> None:
    """Create the singleton profile if it does not already exist.

    Args:
        client: FastAPI test client.
    """

    existing_response = client.get("/api/v1/profile")
    if existing_response.status_code == 200:
        return

    create_response = client.post(
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
    assert create_response.status_code == 201
