"""Frontend state models for job intake and analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobIntakeDraft:
    """Editable job intake input values."""

    title: str = ""
    company: str | None = None
    description: str = ""
    job_url: str | None = None
    language: str = "en"
    notes: str | None = None
    use_llm_analysis: bool = False


@dataclass
class JobState:
    """State container for job intake, analysis, and tailoring selections."""

    intake: JobIntakeDraft = field(default_factory=JobIntakeDraft)
    job_post: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    tailoring_plan: dict[str, Any] | None = None
    snapshot: dict[str, Any] | None = None
    generated_documents: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def extracted_requirements(self) -> list[dict[str, Any]]:
        """Return extracted requirements from loaded analysis payload.

        Returns:
            Requirement list, or an empty list when analysis is missing.
        """

        if self.analysis is None:
            return []
        requirements = self.analysis.get("requirements", [])
        return [item for item in requirements if isinstance(item, dict)]

    def missing_requirements(self) -> list[dict[str, Any]]:
        """Return heuristic missing requirements based on low selected evidence.

        Returns:
            Requirements with low or no selected evidence support.
        """

        if self.tailoring_plan is None:
            return []

        selected_text = " ".join(
            item.get("text", "")
            for item in self.tailoring_plan.get("items", [])
            if item.get("is_selected")
        ).lower()

        missing: list[dict[str, Any]] = []
        for requirement in self.extracted_requirements():
            requirement_text = str(requirement.get("text", "")).lower()
            if (
                requirement_text
                and requirement_text not in selected_text
                and requirement.get("is_must_have")
            ):
                missing.append(requirement)
        return missing
