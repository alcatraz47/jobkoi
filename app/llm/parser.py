"""Structured response parsing utilities for LLM outputs."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.errors import LlmResponseFormatError

TModel = TypeVar("TModel", bound=BaseModel)

_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", flags=re.DOTALL)


def parse_structured_output(raw_text: str, schema: type[TModel]) -> TModel:
    """Parse model output text into a validated Pydantic schema.

    Args:
        raw_text: Raw model output string.
        schema: Target Pydantic schema class.

    Returns:
        Parsed and validated schema instance.

    Raises:
        LlmResponseFormatError: If JSON extraction or schema validation fails.
    """

    payload = _extract_json_payload(raw_text)
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LlmResponseFormatError("Model output is not valid JSON.") from exc

    try:
        return schema.model_validate(decoded)
    except ValidationError as exc:
        raise LlmResponseFormatError("Model output does not match expected structure.") from exc


def _extract_json_payload(raw_text: str) -> str:
    """Extract JSON payload from raw model output.

    Args:
        raw_text: Raw model output string.

    Returns:
        JSON payload text.

    Raises:
        LlmResponseFormatError: If no JSON object or array can be found.
    """

    stripped = raw_text.strip()
    if not stripped:
        raise LlmResponseFormatError("Model output is empty.")

    if _looks_like_json(stripped):
        return stripped

    fenced_match = _JSON_FENCE_PATTERN.search(stripped)
    if fenced_match is not None:
        return fenced_match.group(1).strip()

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        return stripped[object_start : object_end + 1]

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        return stripped[array_start : array_end + 1]

    raise LlmResponseFormatError("Model output does not contain a JSON payload.")


def _looks_like_json(text: str) -> bool:
    """Check whether a string already appears to be raw JSON.

    Args:
        text: Candidate text.

    Returns:
        True when text starts and ends with JSON object or array delimiters.
    """

    return (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    )
