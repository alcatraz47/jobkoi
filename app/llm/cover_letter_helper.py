"""Cover letter generation helper backed by Ollama."""

from __future__ import annotations

from app.llm.client import OllamaClient
from app.llm.contracts import CoverLetterResponse
from app.llm.prompt_factory import PromptFactory


class CoverLetterHelper:
    """Helper for generating structured cover letter text."""

    def __init__(self, client: OllamaClient, prompt_factory: PromptFactory | None = None) -> None:
        """Initialize helper with Ollama client.

        Args:
            client: Configured Ollama client.
            prompt_factory: Optional prompt factory override.
        """

        self._client = client
        self._prompt_factory = prompt_factory or PromptFactory()

    def generate_cover_letter(
        self,
        *,
        job_title: str,
        company: str | None,
        selected_facts: dict[str, str],
        target_language: str,
    ) -> CoverLetterResponse:
        """Generate a structured cover letter from selected facts.

        Args:
            job_title: Target role title.
            company: Optional company name.
            selected_facts: Allowed source facts.
            target_language: Target language code.

        Returns:
            Structured cover letter response.
        """

        prompts = self._prompt_factory.build_cover_letter_prompt(
            job_title=job_title,
            company=company,
            selected_facts=selected_facts,
            target_language=target_language,
        )
        return self._client.generate_structured(
            prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            schema=CoverLetterResponse,
            temperature=0.2,
        )
