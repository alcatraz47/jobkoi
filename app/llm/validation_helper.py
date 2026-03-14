"""Validation helper for model-assisted content checks."""

from __future__ import annotations

from app.llm.client import OllamaClient
from app.llm.contracts import ValidationResponse
from app.llm.prompt_factory import PromptFactory


class ValidationHelper:
    """Helper for validating generated content against allowed facts."""

    def __init__(self, client: OllamaClient, prompt_factory: PromptFactory | None = None) -> None:
        """Initialize helper with Ollama client.

        Args:
            client: Configured Ollama client.
            prompt_factory: Optional prompt factory override.
        """

        self._client = client
        self._prompt_factory = prompt_factory or PromptFactory()

    def validate_generated_text(
        self,
        *,
        text: str,
        allowed_facts: dict[str, str],
        target_language: str,
    ) -> ValidationResponse:
        """Validate generated content using model-assisted checks.

        Args:
            text: Generated text to validate.
            allowed_facts: Allowed source fact mapping.
            target_language: Target language code.

        Returns:
            Structured validation response.
        """

        prompts = self._prompt_factory.build_validation_prompt(
            text=text,
            allowed_facts=allowed_facts,
            target_language=target_language,
        )
        return self._client.generate_structured(
            prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            schema=ValidationResponse,
            temperature=0.0,
        )
