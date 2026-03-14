"""Optional adapters for LLM-assisted job analysis extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LlmRequirementSuggestion:
    """Structured requirement suggestion returned by an LLM adapter.

    Attributes:
        text: Requirement text.
        requirement_type: Requirement category.
        is_must_have: Must-have classification.
        priority_score: Suggested priority score.
    """

    text: str
    requirement_type: str
    is_must_have: bool
    priority_score: int


class JobAnalysisLlmAdapter(Protocol):
    """Protocol for optional LLM-assisted requirement extraction."""

    def extract_requirements(
        self,
        *,
        title: str,
        description: str,
        detected_language: str,
    ) -> list[LlmRequirementSuggestion]:
        """Extract additional requirement suggestions from model output.

        Args:
            title: Job title.
            description: Raw job description.
            detected_language: Language selected in deterministic preprocessing.

        Returns:
            Structured model suggestions.
        """
