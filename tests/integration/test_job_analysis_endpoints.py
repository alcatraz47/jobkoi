"""Integration tests for job submission and job analysis endpoints."""

from __future__ import annotations

from typing import TypeVar

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.llm.errors import LlmTransportError

TModel = TypeVar("TModel", bound=BaseModel)


class _SuccessfulLlmClient:
    """Fake Ollama client returning one structured requirement suggestion."""

    def generate_structured(
        self,
        *,
        prompt: str,
        system_prompt: str,
        schema: type[TModel],
        temperature: float = 0.0,
    ) -> TModel:
        """Return valid structured requirement extraction response."""

        _ = (prompt, system_prompt, temperature)
        return schema.model_validate(
            {
                "requirements": [
                    {
                        "text": "Experience with distributed tracing.",
                        "requirement_type": "skill",
                        "is_must_have": False,
                        "priority_score": 55,
                    }
                ]
            }
        )


class _FailingLlmClient:
    """Fake Ollama client raising transport errors."""

    def generate_structured(
        self,
        *,
        prompt: str,
        system_prompt: str,
        schema: type[TModel],
        temperature: float = 0.0,
    ) -> TModel:
        """Raise transport failure to simulate unavailable Ollama."""

        _ = (prompt, system_prompt, schema, temperature)
        raise LlmTransportError("simulated transport failure")


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


def test_analysis_with_llm_merges_llm_requirements(client: TestClient, monkeypatch) -> None:
    """LLM-enabled analysis should include persisted requirements marked as llm source."""

    monkeypatch.setattr(
        "app.api.routers.job_analyses.get_ollama_client",
        lambda: _SuccessfulLlmClient(),
    )

    create_job_response = client.post(
        "/api/v1/job-posts",
        json={
            "title": "Backend Engineer",
            "company": "Example GmbH",
            "description": "Must have Python and SQL.",
        },
    )
    assert create_job_response.status_code == 201
    job_post_id = create_job_response.json()["id"]

    analyze_response = client.post(
        f"/api/v1/job-posts/{job_post_id}/analyses",
        json={"use_llm": True},
    )
    assert analyze_response.status_code == 201

    requirements = analyze_response.json()["requirements"]
    assert any(item["source"] == "llm" for item in requirements)


def test_analysis_with_llm_returns_503_on_transport_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    """LLM-enabled analysis should return 503 when Ollama is unavailable."""

    monkeypatch.setattr(
        "app.api.routers.job_analyses.get_ollama_client",
        lambda: _FailingLlmClient(),
    )

    create_job_response = client.post(
        "/api/v1/job-posts",
        json={
            "title": "Backend Engineer",
            "company": "Example GmbH",
            "description": "Must have Python and SQL.",
        },
    )
    assert create_job_response.status_code == 201
    job_post_id = create_job_response.json()["id"]

    analyze_response = client.post(
        f"/api/v1/job-posts/{job_post_id}/analyses",
        json={"use_llm": True},
    )
    assert analyze_response.status_code == 503
    assert "LLM service unavailable" in analyze_response.json()["detail"]
