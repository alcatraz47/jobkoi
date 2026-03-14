"""Unit tests for Ollama client and LLM helper adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

import httpx
import pytest
from pydantic import BaseModel

from app.llm.client import OllamaClient, OllamaClientSettings
from app.llm.contracts import (
    CoverLetterResponse,
    CvRewriteResponse,
    FactRewriteResponse,
    RequirementExtractionResponse,
    ValidationResponse,
)
from app.llm.cover_letter_helper import CoverLetterHelper
from app.llm.errors import LlmResponseFormatError, LlmTransportError
from app.llm.extraction_helper import ExtractionHelper
from app.llm.rewrite_helper import CvRewriteHelper, TailoringRewriteHelper
from app.llm.validation_helper import ValidationHelper

TModel = TypeVar("TModel", bound=BaseModel)


class FakeStructuredClient:
    """Fake client returning predefined structured responses."""

    def __init__(self, response: BaseModel) -> None:
        """Initialize fake client with fixed response payload.

        Args:
            response: Response model returned for every structured call.
        """

        self._response = response
        self.calls: list[tuple[str, str, type[BaseModel], float]] = []

    def generate_structured(
        self,
        *,
        prompt: str,
        system_prompt: str,
        schema: type[TModel],
        temperature: float = 0.0,
    ) -> TModel:
        """Return configured response converted to requested schema.

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            schema: Expected schema.
            temperature: Requested temperature.

        Returns:
            Parsed schema instance.
        """

        self.calls.append((prompt, system_prompt, cast(type[BaseModel], schema), temperature))
        return schema.model_validate(self._response.model_dump())


def test_ollama_client_parses_structured_response_via_mock_transport() -> None:
    """Client should parse structured JSON content from Ollama envelope."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return fixed successful Ollama-like response."""

        assert request.url.path == "/api/chat"
        content = (
            '{"requirements": ['
            '{"text": "Python", "requirement_type": "skill", '
            '"is_must_have": true, "priority_score": 90}]}'
        )
        return httpx.Response(200, json={"message": {"content": content}})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, timeout=5.0)
    client = OllamaClient(
        settings=OllamaClientSettings(base_url="http://ollama.local", model="mock", max_retries=0),
        http_client=http_client,
    )

    result = client.generate_structured(
        prompt="extract",
        system_prompt="system",
        schema=RequirementExtractionResponse,
    )

    assert len(result.requirements) == 1
    assert result.requirements[0].text == "Python"


def test_ollama_client_retries_structured_parse_errors() -> None:
    """Client should retry structured calls after format errors."""

    responses = [
        {"message": {"content": "not-json"}},
        {
            "message": {
                "content": (
                    '{"requirements": ['
                    '{"text": "SQL", "requirement_type": "skill", '
                    '"is_must_have": false, "priority_score": 60}]}'
                )
            }
        },
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        """Return queued responses for retry behavior."""

        payload = responses.pop(0)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, timeout=5.0)
    client = OllamaClient(
        settings=OllamaClientSettings(base_url="http://ollama.local", model="mock", max_retries=1),
        http_client=http_client,
    )

    result = client.generate_structured(
        prompt="extract",
        system_prompt="system",
        schema=RequirementExtractionResponse,
    )

    assert len(result.requirements) == 1
    assert result.requirements[0].text == "SQL"


def test_ollama_client_raises_transport_error_for_http_failures() -> None:
    """Client should raise transport error for non-success responses."""

    def handler(_: httpx.Request) -> httpx.Response:
        """Return failed response envelope."""

        return httpx.Response(500, text="internal error")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, timeout=5.0)
    client = OllamaClient(
        settings=OllamaClientSettings(base_url="http://ollama.local", model="mock", max_retries=0),
        http_client=http_client,
    )

    with pytest.raises(LlmTransportError):
        client.generate_text(prompt="hello", system_prompt="system")


def test_extraction_helper_uses_structured_client_contract() -> None:
    """Extraction helper should return typed extraction response."""

    fake_client = FakeStructuredClient(
        RequirementExtractionResponse(
            requirements=[
                {
                    "text": "FastAPI",
                    "requirement_type": "skill",
                    "is_must_have": True,
                    "priority_score": 88,
                }
            ]
        )
    )
    helper = ExtractionHelper(cast(OllamaClient, fake_client))

    response = helper.extract_requirements(
        title="Backend Engineer",
        description="Must have FastAPI",
        detected_language="en",
    )

    assert len(response.requirements) == 1
    assert response.requirements[0].text == "FastAPI"


def test_cv_rewrite_helper_returns_structured_payload() -> None:
    """CV rewrite helper should return structured summary and bullets."""

    fake_client = FakeStructuredClient(
        CvRewriteResponse(summary="Rewritten summary", bullets=["Bullet one", "Bullet two"])
    )
    helper = CvRewriteHelper(cast(OllamaClient, fake_client))

    response = helper.rewrite_summary_and_bullets(
        summary="Old summary",
        bullets=["Old bullet"],
        selected_facts={"fact:1": "Built APIs"},
        target_language="en",
    )

    assert response.summary == "Rewritten summary"
    assert response.bullets == ["Bullet one", "Bullet two"]


def test_tailoring_rewrite_helper_filters_unknown_fact_keys() -> None:
    """Tailoring rewrite helper should ignore rewrites for unknown keys."""

    fake_client = FakeStructuredClient(
        FactRewriteResponse(
            rewrites=[
                {"fact_key": "fact:1", "rewritten_text": "Known rewrite"},
                {"fact_key": "fact:999", "rewritten_text": "Unknown rewrite"},
            ]
        )
    )
    helper = TailoringRewriteHelper(cast(OllamaClient, fake_client))

    rewrites = helper.rewrite_selected_facts(
        selected_facts={"fact:1": "Original"},
        target_language="en",
    )

    assert rewrites == {"fact:1": "Known rewrite"}


def test_cover_letter_and_validation_helpers_return_typed_models() -> None:
    """Cover letter and validation helpers should return typed contracts."""

    cover_client = FakeStructuredClient(CoverLetterResponse(cover_letter="Dear Hiring Team,"))
    cover_helper = CoverLetterHelper(cast(OllamaClient, cover_client))

    letter = cover_helper.generate_cover_letter(
        job_title="Backend Engineer",
        company="Example GmbH",
        selected_facts={"fact:1": "Built APIs"},
        target_language="en",
    )
    assert letter.cover_letter.startswith("Dear")

    validation_client = FakeStructuredClient(
        ValidationResponse(
            is_valid=False,
            issues=[
                {
                    "issue_type": "unsupported_claim",
                    "message": "Claim not found in allowed facts.",
                    "severity": "high",
                    "fact_key": None,
                }
            ],
        )
    )
    validation_helper = ValidationHelper(cast(OllamaClient, validation_client))

    validation = validation_helper.validate_generated_text(
        text="Built 20 systems.",
        allowed_facts={"fact:1": "Built APIs"},
        target_language="en",
    )

    assert validation.is_valid is False
    assert validation.issues[0].issue_type == "unsupported_claim"
