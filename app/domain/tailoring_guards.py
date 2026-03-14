"""Factual safety guards for tailored snapshot construction."""

from __future__ import annotations

import re
from typing import Final

from app.domain.job_text import normalize_text

_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b\d+\+?\b")


class InventedClaimError(ValueError):
    """Raised when rewritten content introduces unsupported claims."""


def validate_rewrites_against_selected_facts(
    *,
    selected_fact_texts: dict[str, str],
    rewrites: dict[str, str],
) -> None:
    """Validate rewrite payload against selected source facts.

    The guard enforces that rewrites can only target selected facts and cannot
    introduce new numeric claims that were not present in the source text.

    Args:
        selected_fact_texts: Mapping of selected fact keys to original text.
        rewrites: Mapping of fact keys to rewritten text.

    Raises:
        InventedClaimError: If rewrites reference unselected facts or add new numeric claims.
    """

    selected_keys = set(selected_fact_texts)
    for fact_key, rewritten_text in rewrites.items():
        if fact_key not in selected_keys:
            raise InventedClaimError(f"Rewrite fact key is not selected: {fact_key}")

        normalized_rewrite = normalize_text(rewritten_text)
        if not normalized_rewrite:
            raise InventedClaimError(f"Rewrite text is empty for fact: {fact_key}")

        source_text = selected_fact_texts[fact_key]
        _assert_no_new_numeric_claims(source_text=source_text, rewritten_text=normalized_rewrite)


def _assert_no_new_numeric_claims(*, source_text: str, rewritten_text: str) -> None:
    """Reject rewrite text that introduces new numeric claims.

    Args:
        source_text: Original selected source text.
        rewritten_text: Candidate rewritten text.

    Raises:
        InventedClaimError: If rewritten text contains new number tokens.
    """

    source_numbers = set(_NUMBER_PATTERN.findall(source_text))
    rewritten_numbers = set(_NUMBER_PATTERN.findall(rewritten_text))
    new_numbers = rewritten_numbers - source_numbers
    if new_numbers:
        raise InventedClaimError(
            "Rewritten content introduced unsupported numeric claims: "
            + ", ".join(sorted(new_numbers))
        )
