"""Integration tests for health endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class _HealthyLlmClient:
    """Fake Ollama client representing healthy server/model state."""

    def get_server_version(self) -> str:
        """Return synthetic Ollama version."""

        return "0.0.1"

    def is_model_available(self) -> bool:
        """Return model availability flag."""

        return True

    def warmup_model(self) -> str:
        """Return synthetic warm-up completion text."""

        return "OK"


class _ModelMissingLlmClient:
    """Fake Ollama client representing missing local model state."""

    def get_server_version(self) -> str:
        """Return synthetic Ollama version."""

        return "0.0.1"

    def is_model_available(self) -> bool:
        """Return model availability flag."""

        return False

    def warmup_model(self) -> str:
        """Return synthetic warm-up response when called."""

        return "SKIPPED"


def test_health_returns_ok(client: TestClient) -> None:
    """Base health endpoint should return liveness status."""

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_llm_health_warmup_reports_ok(client: TestClient, monkeypatch) -> None:
    """LLM health endpoint should report OK when server/model/warmup all succeed."""

    monkeypatch.setattr("app.api.routers.health.get_ollama_client", lambda: _HealthyLlmClient())

    response = client.get("/api/v1/health/llm?warmup=true")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["server_reachable"] is True
    assert body["model_available"] is True
    assert body["warmed_up"] is True


def test_llm_health_reports_degraded_when_model_missing(client: TestClient, monkeypatch) -> None:
    """LLM health endpoint should report degraded when configured model is unavailable."""

    monkeypatch.setattr("app.api.routers.health.get_ollama_client", lambda: _ModelMissingLlmClient())

    response = client.get("/api/v1/health/llm")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "degraded"
    assert body["server_reachable"] is True
    assert body["model_available"] is False
