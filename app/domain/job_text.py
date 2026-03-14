"""Text normalization and language detection helpers for job ingestion."""

from __future__ import annotations

import re
from typing import Final

_WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\s+")
_CONTROL_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

_GERMAN_MARKERS: Final[tuple[str, ...]] = (
    "und",
    "oder",
    "mit",
    "für",
    "kenntnisse",
    "erfahrung",
    "anforderungen",
    "muss",
    "sollte",
    "wünschenswert",
)
_ENGLISH_MARKERS: Final[tuple[str, ...]] = (
    "and",
    "or",
    "with",
    "for",
    "experience",
    "requirements",
    "must",
    "should",
    "preferred",
    "nice to have",
)


def strip_control_characters(text: str) -> str:
    """Remove non-printable control characters from text.

    Args:
        text: Input text.

    Returns:
        Text without ASCII control characters.
    """

    return _CONTROL_PATTERN.sub("", text)


def normalize_whitespace(text: str) -> str:
    """Normalize repeated whitespace into single spaces.

    Args:
        text: Input text.

    Returns:
        Text with compacted whitespace.
    """

    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def normalize_text(text: str) -> str:
    """Normalize text for deterministic processing.

    Args:
        text: Input text.

    Returns:
        Cleaned and whitespace-normalized text.
    """

    without_controls = strip_control_characters(text)
    return normalize_whitespace(without_controls)


def split_candidate_lines(text: str) -> list[str]:
    """Split input text into candidate requirement lines.

    Args:
        text: Normalized or raw description text.

    Returns:
        Candidate lines preserving input order.
    """

    normalized = text.replace("\r", "\n")
    chunked = re.split(r"\n|[.;]\s+", normalized)
    lines: list[str] = []
    for line in chunked:
        compact = normalize_whitespace(line)
        if len(compact) < 3:
            continue
        lines.append(compact)
    return lines


def detect_language_fallback(text: str, default_language: str = "en") -> str:
    """Detect whether a text is likely English or German.

    The detector is deterministic and intentionally lightweight.

    Args:
        text: Source text.
        default_language: Language used when confidence is weak.

    Returns:
        ``"de"`` for German or ``"en"`` for English.
    """

    lowered = normalize_text(text).lower()
    if not lowered:
        return default_language

    german_score = _count_markers(lowered, _GERMAN_MARKERS)
    english_score = _count_markers(lowered, _ENGLISH_MARKERS)

    umlaut_bonus = 1 if any(char in lowered for char in ("ä", "ö", "ü", "ß")) else 0
    german_score += umlaut_bonus

    if german_score > english_score:
        return "de"
    if english_score > german_score:
        return "en"
    return default_language


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    """Count marker occurrences in text.

    Args:
        text: Normalized lower-case text.
        markers: Marker token sequence.

    Returns:
        Number of matched markers.
    """

    return sum(1 for marker in markers if marker in text)
