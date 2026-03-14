"""Pure matching and relevance scoring helpers for tailoring."""

from __future__ import annotations

import re
from typing import Final

from app.domain.job_text import normalize_text
from app.domain.tailoring_types import JobRequirementData

_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-zA-Z0-9+#.]{2,}")

_CANONICAL_PHRASE_MARKERS: Final[dict[str, tuple[str, ...]]] = {
    "nlp": ("natural language processing",),
    "llm": ("large language model", "large language models"),
    "vlm": ("vision language model", "vision language models"),
    "computer_vision": ("computer vision",),
    "ocr": ("optical character recognition",),
}


def tokenize_for_match(text: str) -> set[str]:
    """Tokenize text into normalized matching tokens.

    Args:
        text: Input text.

    Returns:
        Lower-case token set enriched with canonical aliases.
    """

    normalized = normalize_text(text).lower()
    base_tokens = {token for token in _WORD_PATTERN.findall(normalized) if len(token) >= 2}
    return _expand_canonical_tokens(base_tokens=base_tokens, normalized_text=normalized)


def _expand_canonical_tokens(*, base_tokens: set[str], normalized_text: str) -> set[str]:
    """Expand base tokens with canonical alias tokens.

    Args:
        base_tokens: Raw token set from input text.
        normalized_text: Normalized source text.

    Returns:
        Expanded token set used for matching.
    """

    expanded = set(base_tokens)

    for canonical, markers in _CANONICAL_PHRASE_MARKERS.items():
        if any(marker in normalized_text for marker in markers):
            expanded.add(canonical)

    if "nlp" in expanded:
        expanded.add("nlp")

    if "llm" in expanded or "llms" in expanded:
        expanded.add("llm")

    if "vlm" in expanded or "vlms" in expanded:
        expanded.add("vlm")

    if "ci/cd" in normalized_text or {"ci", "cd"}.issubset(expanded):
        expanded.add("ci_cd")

    if "continuous integration" in normalized_text and "continuous deployment" in normalized_text:
        expanded.add("ci_cd")

    if "mlops" in expanded or ("ml" in expanded and "ops" in expanded):
        expanded.add("mlops")

    return expanded


def build_requirement_keyword_set(requirements: list[JobRequirementData]) -> set[str]:
    """Build a keyword set from extracted job requirements.

    Args:
        requirements: Job requirement list.

    Returns:
        Token set used for deterministic matching.
    """

    keywords: set[str] = set()
    for requirement in requirements:
        keywords.update(tokenize_for_match(requirement.text))
    return keywords


def skill_match_score(skill_name: str, requirement_keywords: set[str]) -> float:
    """Compute skill match score against requirement keyword set.

    Args:
        skill_name: Profile skill text.
        requirement_keywords: Requirement token set.

    Returns:
        Score in range ``0.0`` to ``1.0``.
    """

    skill_tokens = tokenize_for_match(skill_name)
    if not skill_tokens or not requirement_keywords:
        return 0.0

    overlap = skill_tokens & requirement_keywords
    return len(overlap) / len(skill_tokens)


def keyword_match_score(text: str, requirement_keywords: set[str]) -> float:
    """Compute keyword overlap score for arbitrary fact text.

    Args:
        text: Fact text.
        requirement_keywords: Requirement token set.

    Returns:
        Score in range ``0.0`` to ``1.0``.
    """

    text_tokens = tokenize_for_match(text)
    if not text_tokens or not requirement_keywords:
        return 0.0

    overlap = text_tokens & requirement_keywords
    return len(overlap) / len(requirement_keywords)


def count_must_have_hits(text: str, requirements: list[JobRequirementData]) -> int:
    """Count how many must-have requirements match the provided text.

    Args:
        text: Fact text to evaluate.
        requirements: Job requirement list.

    Returns:
        Count of matched must-have requirements.
    """

    text_tokens = tokenize_for_match(text)
    hits = 0
    for requirement in requirements:
        if not requirement.is_must_have:
            continue
        requirement_tokens = tokenize_for_match(requirement.text)
        if requirement_tokens & text_tokens:
            hits += 1
    return hits


def compute_relevance_score(
    *,
    skill_score: float,
    keyword_score: float,
    must_have_hits: int,
) -> int:
    """Compute deterministic relevance score for tailoring fact ranking.

    Args:
        skill_score: Skill score in range ``0.0`` to ``1.0``.
        keyword_score: Keyword overlap score in range ``0.0`` to ``1.0``.
        must_have_hits: Number of must-have matches.

    Returns:
        Integer relevance score in range ``0`` to ``100``.
    """

    raw = (skill_score * 45.0) + (keyword_score * 45.0) + (must_have_hits * 10.0)
    bounded = max(0.0, min(100.0, raw))
    return int(round(bounded))
