"""Structured extraction helper backed by Ollama client."""

from __future__ import annotations

from app.llm.client import OllamaClient
from app.llm.contracts import RequirementExtractionResponse
from app.llm.job_analysis_adapter import JobAnalysisLlmAdapter, LlmRequirementSuggestion
from app.llm.prompt_factory import PromptFactory


class ExtractionHelper:
    """Helper for structured requirement extraction."""

    def __init__(self, client: OllamaClient, prompt_factory: PromptFactory | None = None) -> None:
        """Initialize extraction helper.

        Args:
            client: Configured Ollama client.
            prompt_factory: Optional prompt factory override.
        """

        self._client = client
        self._prompt_factory = prompt_factory or PromptFactory()

    def extract_requirements(
        self,
        *,
        title: str,
        description: str,
        detected_language: str,
    ) -> RequirementExtractionResponse:
        """Extract structured job requirements from job text.

        Args:
            title: Job title.
            description: Job description.
            detected_language: Input language code.

        Returns:
            Structured extraction response.
        """

        prompts = self._prompt_factory.build_requirement_extraction_prompt(
            title=title,
            description=description,
            detected_language=detected_language,
        )
        return self._client.generate_structured(
            prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            schema=RequirementExtractionResponse,
            temperature=0.0,
        )


class OllamaJobAnalysisAdapter(JobAnalysisLlmAdapter):
    """Adapter implementation for optional job-analysis LLM enrichment."""

    def __init__(self, helper: ExtractionHelper) -> None:
        """Initialize adapter with extraction helper.

        Args:
            helper: Extraction helper instance.
        """

        self._helper = helper

    def extract_requirements(
        self,
        *,
        title: str,
        description: str,
        detected_language: str,
    ) -> list[LlmRequirementSuggestion]:
        """Extract requirement suggestions for analysis enrichment.

        Args:
            title: Job title.
            description: Job description.
            detected_language: Input language code.

        Returns:
            Requirement suggestion list.
        """

        result = self._helper.extract_requirements(
            title=title,
            description=description,
            detected_language=detected_language,
        )
        return [
            LlmRequirementSuggestion(
                text=item.text,
                requirement_type=item.requirement_type,
                is_must_have=item.is_must_have,
                priority_score=item.priority_score,
            )
            for item in result.requirements
        ]
