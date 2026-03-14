"""Optional adapter interface for LLM-assisted tailoring rewrites."""

from __future__ import annotations

from typing import Protocol


class TailoringRewriteLlmAdapter(Protocol):
    """Protocol for model-assisted rewriting of selected profile facts."""

    def rewrite_selected_facts(
        self,
        *,
        selected_facts: dict[str, str],
        target_language: str,
    ) -> dict[str, str]:
        """Rewrite selected facts while preserving original meaning.

        Args:
            selected_facts: Selected fact text keyed by stable fact key.
            target_language: Output language code.

        Returns:
            Mapping of fact keys to rewritten text.
        """
