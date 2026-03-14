"""Unit tests for structured LLM response parsing."""

from __future__ import annotations

import pytest

from app.llm.contracts import RequirementExtractionResponse
from app.llm.errors import LlmResponseFormatError
from app.llm.parser import parse_structured_output


def test_parse_structured_output_accepts_plain_json() -> None:
    """Parser should accept valid JSON payload text."""

    raw = (
        '{"requirements": ['
        '{"text": "Python", "requirement_type": "skill", '
        '"is_must_have": true, "priority_score": 90}]}'
    )

    parsed = parse_structured_output(raw, RequirementExtractionResponse)

    assert len(parsed.requirements) == 1
    assert parsed.requirements[0].text == "Python"


def test_parse_structured_output_accepts_markdown_json_fence() -> None:
    """Parser should extract JSON payload from fenced markdown output."""

    raw = """
    ```json
    {
      "requirements": [
        {"text": "FastAPI", "requirement_type": "skill", "is_must_have": false, "priority_score": 50}
      ]
    }
    ```
    """

    parsed = parse_structured_output(raw, RequirementExtractionResponse)

    assert len(parsed.requirements) == 1
    assert parsed.requirements[0].requirement_type == "skill"


def test_parse_structured_output_raises_for_invalid_structure() -> None:
    """Parser should raise when output does not match expected schema."""

    raw = '{"wrong_key": []}'

    with pytest.raises(LlmResponseFormatError):
        parse_structured_output(raw, RequirementExtractionResponse)
