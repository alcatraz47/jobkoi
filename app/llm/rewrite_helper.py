"""Rewrite helpers for CV content and selected tailoring facts."""

from __future__ import annotations

from app.llm.client import OllamaClient
from app.llm.contracts import CvRewriteResponse, FactRewriteResponse
from app.llm.prompt_factory import PromptFactory
from app.llm.tailoring_rewrite_adapter import TailoringRewriteLlmAdapter


class CvRewriteHelper:
    """Helper for rewriting CV summary and bullet content."""

    def __init__(self, client: OllamaClient, prompt_factory: PromptFactory | None = None) -> None:
        """Initialize helper with Ollama client.

        Args:
            client: Configured Ollama client.
            prompt_factory: Optional prompt factory override.
        """

        self._client = client
        self._prompt_factory = prompt_factory or PromptFactory()

    def rewrite_summary_and_bullets(
        self,
        *,
        summary: str | None,
        bullets: list[str],
        selected_facts: dict[str, str],
        target_language: str,
    ) -> CvRewriteResponse:
        """Rewrite CV summary and bullets using selected source facts.

        Args:
            summary: Existing summary text.
            bullets: Existing bullet lines.
            selected_facts: Allowed source facts.
            target_language: Target language code.

        Returns:
            Structured CV rewrite response.
        """

        prompts = self._prompt_factory.build_cv_rewrite_prompt(
            summary=summary,
            bullets=bullets,
            selected_facts=selected_facts,
            target_language=target_language,
        )
        return self._client.generate_structured(
            prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            schema=CvRewriteResponse,
            temperature=0.2,
        )


class TailoringRewriteHelper(TailoringRewriteLlmAdapter):
    """Adapter for rewriting selected tailoring facts with Ollama."""

    def __init__(self, client: OllamaClient, prompt_factory: PromptFactory | None = None) -> None:
        """Initialize helper with Ollama client.

        Args:
            client: Configured Ollama client.
            prompt_factory: Optional prompt factory override.
        """

        self._client = client
        self._prompt_factory = prompt_factory or PromptFactory()

    def rewrite_selected_facts(
        self,
        *,
        selected_facts: dict[str, str],
        target_language: str,
    ) -> dict[str, str]:
        """Rewrite selected facts and return mapping by fact key.

        Args:
            selected_facts: Selected source fact mapping.
            target_language: Target language code.

        Returns:
            Fact rewrite mapping filtered to selected keys.
        """

        prompts = self._prompt_factory.build_fact_rewrite_prompt(
            selected_facts=selected_facts,
            target_language=target_language,
        )
        response = self._client.generate_structured(
            prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            schema=FactRewriteResponse,
            temperature=0.2,
        )

        allowed = set(selected_facts)
        return {
            item.fact_key: item.rewritten_text
            for item in response.rewrites
            if item.fact_key in allowed
        }
