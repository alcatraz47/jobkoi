"""Prompt construction helpers for local Ollama interactions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptBundle:
    """Prompt bundle containing system and user prompt strings.

    Attributes:
        system_prompt: Stable system-level instruction text.
        user_prompt: Task-specific user instruction text.
    """

    system_prompt: str
    user_prompt: str


class PromptFactory:
    """Factory for task-specific prompt bundles.

    The factory only formats instructions and payload context. It does not execute
    model calls or make orchestration decisions.
    """

    def build_requirement_extraction_prompt(
        self,
        *,
        title: str,
        description: str,
        detected_language: str,
    ) -> PromptBundle:
        """Create prompt bundle for structured requirement extraction.

        Args:
            title: Job title.
            description: Job description text.
            detected_language: Input language code.

        Returns:
            Prompt bundle for extraction.
        """

        system_prompt = (
            "You extract job requirements from provided text. "
            "Return strict JSON only. Do not include markdown."
        )
        user_prompt = (
            "Task: extract requirements from the job text.\n"
            "Language: "
            f"{detected_language}\n"
            "Output schema: {\"requirements\": ["
            "{\"text\": str, \"requirement_type\": str, \"is_must_have\": bool, "
            "\"priority_score\": int}]}\n"
            "Job title:\n"
            f"{title}\n"
            "Job description:\n"
            f"{description}"
        )
        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_profile_import_extraction_prompt(
        self,
        *,
        source_type: str,
        source_label: str,
        detected_language: str,
        raw_text: str,
    ) -> PromptBundle:
        """Create prompt bundle for structured profile import extraction.

        Args:
            source_type: Source type such as ``cv_document``.
            source_label: Human-readable source label.
            detected_language: Detected source language code.
            raw_text: Extracted source text.

        Returns:
            Prompt bundle for structured profile extraction.
        """

        system_prompt = (
            "You extract structured profile facts from resume text. "
            "Return strict JSON only. Do not include markdown. "
            "Never invent facts, metrics, responsibilities, education, or skills. "
            "Only output values explicitly supported by the provided text. "
            "If uncertain, omit the field."
        )

        user_prompt = (
            "Task: extract profile data from the provided import text.\n"
            f"Source type: {source_type}\n"
            f"Source label: {source_label}\n"
            f"Language: {detected_language}\n"
            "Rules:\n"
            "1) Use only provided text evidence.\n"
            "2) Do not infer missing facts.\n"
            "3) Use concise values (company name only, title only, skill label only).\n"
            "4) Keep at most 20 experiences, 10 educations, 40 skills.\n"
            "5) For scalar fields include evidence objects when possible.\n"
            "Output schema:\n"
            "{\n"
            "  \"full_name\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"email\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"phone\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"location\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"headline\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"summary\": {\"value\": str, \"source_excerpt\": str | null, \"source_locator\": str | null} | null,\n"
            "  \"experiences\": [{\"company\": str | null, \"title\": str | null, \"start_date\": str | null, \"end_date\": str | null, \"description\": str | null, \"source_excerpt\": str | null, \"source_locator\": str | null}],\n"
            "  \"educations\": [{\"institution\": str | null, \"degree\": str | null, \"field_of_study\": str | null, \"start_date\": str | null, \"end_date\": str | null, \"source_excerpt\": str | null, \"source_locator\": str | null}],\n"
            "  \"skills\": [{\"skill_name\": str, \"level\": str | null, \"category\": str | null, \"source_excerpt\": str | null, \"source_locator\": str | null}]\n"
            "}\n"
            "Source text:\n"
            f"{raw_text}"
        )

        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_profile_import_audit_prompt(
        self,
        *,
        source_type: str,
        source_label: str,
        detected_language: str,
        candidate_profile_json: str,
        raw_text: str,
    ) -> PromptBundle:
        """Create prompt bundle for profile-import supervision and scalar correction.

        Args:
            source_type: Source type such as ``cv_document``.
            source_label: Human-readable source label.
            detected_language: Detected source language code.
            candidate_profile_json: JSON string for current extracted candidate.
            raw_text: Extracted source text.

        Returns:
            Prompt bundle for structured profile-audit suggestions.
        """

        system_prompt = (
            "You audit an extracted candidate profile against source text. "
            "Return strict JSON only. Do not include markdown. "
            "Never invent facts. Suggest only values explicitly present in source text."
        )

        user_prompt = (
            "Task: review scalar placement quality for extracted profile data.\n"
            f"Source type: {source_type}\n"
            f"Source label: {source_label}\n"
            f"Language: {detected_language}\n"
            "Rules:\n"
            "1) Focus only on scalar fields: full_name, email, phone, location, headline, summary.\n"
            "2) Use action 'drop' if value is unsupported/noisy.\n"
            "3) Use action 'replace' only with an explicitly present source value.\n"
            "4) Use move_to_education when an education-like value is wrongly placed in location/headline/summary.\n"
            "5) Keep suggestions small and high precision.\n"
            "Output schema:\n"
            "{\n"
            "  \"scalar_suggestions\": [\n"
            "    {\"field_name\": \"full_name|email|phone|location|headline|summary\", "
            "\"action\": \"keep|drop|replace|move_to_location|move_to_headline|move_to_summary|move_to_education\", "
            "\"suggested_value\": str | null, \"reason\": str | null}\n"
            "  ],\n"
            "  \"missing_signals\": [str],\n"
            "  \"warnings\": [str]\n"
            "}\n"
            "Current extracted candidate JSON:\n"
            f"{candidate_profile_json}\n"
            "Source text:\n"
            f"{raw_text}"
        )

        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_cv_rewrite_prompt(
        self,
        *,
        summary: str | None,
        bullets: list[str],
        selected_facts: dict[str, str],
        target_language: str,
    ) -> PromptBundle:
        """Create prompt bundle for rewriting CV summary and bullets.

        Args:
            summary: Existing summary text.
            bullets: Existing bullet lines.
            selected_facts: Allowed source facts keyed by fact key.
            target_language: Target language code.

        Returns:
            Prompt bundle for CV rewrite.
        """

        facts_block = _format_fact_block(selected_facts)
        summary_text = summary or ""
        bullets_text = "\n".join(f"- {bullet}" for bullet in bullets)

        system_prompt = (
            "You rewrite CV summary and bullets using only allowed facts. "
            "Do not invent claims. Return strict JSON only."
        )
        user_prompt = (
            "Task: rewrite summary and bullets in target language while preserving facts.\n"
            f"Target language: {target_language}\n"
            "Output schema: {\"summary\": str | null, \"bullets\": [str]}\n"
            "Allowed facts:\n"
            f"{facts_block}\n"
            "Current summary:\n"
            f"{summary_text}\n"
            "Current bullets:\n"
            f"{bullets_text}"
        )
        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_fact_rewrite_prompt(
        self,
        *,
        selected_facts: dict[str, str],
        target_language: str,
    ) -> PromptBundle:
        """Create prompt bundle for rewriting selected fact texts.

        Args:
            selected_facts: Selected fact text keyed by fact key.
            target_language: Target language code.

        Returns:
            Prompt bundle for fact rewriting.
        """

        facts_block = _format_fact_block(selected_facts)
        system_prompt = (
            "You rewrite selected facts with clearer language while preserving meaning. "
            "Use only provided facts. Return strict JSON only."
        )
        user_prompt = (
            "Task: rewrite each selected fact in target language.\n"
            f"Target language: {target_language}\n"
            "Output schema: {\"rewrites\": [{\"fact_key\": str, \"rewritten_text\": str}]}\n"
            "Selected facts:\n"
            f"{facts_block}"
        )
        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_cover_letter_prompt(
        self,
        *,
        job_title: str,
        company: str | None,
        selected_facts: dict[str, str],
        target_language: str,
    ) -> PromptBundle:
        """Create prompt bundle for cover letter generation.

        Args:
            job_title: Target role title.
            company: Optional company name.
            selected_facts: Allowed source facts keyed by fact key.
            target_language: Target language code.

        Returns:
            Prompt bundle for cover letter generation.
        """

        facts_block = _format_fact_block(selected_facts)
        company_text = company or "Unknown company"
        system_prompt = (
            "You generate concise cover letter text using only allowed facts. "
            "Do not invent experience or metrics. Return strict JSON only."
        )
        user_prompt = (
            "Task: generate a concise cover letter body.\n"
            f"Target language: {target_language}\n"
            f"Role: {job_title}\n"
            f"Company: {company_text}\n"
            "Output schema: {\"cover_letter\": str}\n"
            "Allowed facts:\n"
            f"{facts_block}"
        )
        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)

    def build_validation_prompt(
        self,
        *,
        text: str,
        allowed_facts: dict[str, str],
        target_language: str,
    ) -> PromptBundle:
        """Create prompt bundle for validation checks on generated text.

        Args:
            text: Generated text to validate.
            allowed_facts: Allowed source facts keyed by fact key.
            target_language: Target language code.

        Returns:
            Prompt bundle for validation.
        """

        facts_block = _format_fact_block(allowed_facts)
        system_prompt = (
            "You validate generated application text against allowed facts. "
            "Flag unsupported claims and language issues. Return strict JSON only."
        )
        user_prompt = (
            "Task: validate generated text against allowed facts.\n"
            f"Target language: {target_language}\n"
            "Output schema: {\"is_valid\": bool, \"issues\": "
            "[{\"issue_type\": str, \"message\": str, \"severity\": "
            "\"low\"|\"medium\"|\"high\", \"fact_key\": str | null}]}\n"
            "Allowed facts:\n"
            f"{facts_block}\n"
            "Generated text:\n"
            f"{text}"
        )
        return PromptBundle(system_prompt=system_prompt, user_prompt=user_prompt)


def _format_fact_block(facts: dict[str, str]) -> str:
    """Format fact mapping into deterministic prompt text.

    Args:
        facts: Fact mapping keyed by stable identifiers.

    Returns:
        Multi-line fact block.
    """

    if not facts:
        return "(no facts provided)"

    lines = [f"{key}: {value}" for key, value in sorted(facts.items())]
    return "\n".join(lines)
