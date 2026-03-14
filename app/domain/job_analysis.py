"""Deterministic structured job analysis builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.domain.job_text import normalize_text, split_candidate_lines

_MUST_HAVE_MARKERS: Final[tuple[str, ...]] = (
    "must",
    "required",
    "mandatory",
    "need to",
    "you have",
    "erforderlich",
    "muss",
    "voraussetzung",
)

_NICE_TO_HAVE_MARKERS: Final[tuple[str, ...]] = (
    "nice to have",
    "preferred",
    "bonus",
    "plus",
    "ideally",
    "wünschenswert",
    "von vorteil",
)

_SKILL_MARKERS: Final[tuple[str, ...]] = (
    "python",
    "sql",
    "java",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "fastapi",
    "django",
)


@dataclass(frozen=True)
class RequirementDraft:
    """Structured requirement extracted from job text.

    Attributes:
        text: Human-readable requirement text.
        normalized_text: Canonical requirement text for deduplication.
        requirement_type: Logical category, for example ``skill`` or ``experience``.
        is_must_have: True when requirement appears mandatory.
        priority_score: Relative ranking score from 0 to 100.
        source_line_index: Source line position in extracted candidate lines.
        source: Origin of extraction.
    """

    text: str
    normalized_text: str
    requirement_type: str
    is_must_have: bool
    priority_score: int
    source_line_index: int
    source: str = "rule_based"


@dataclass(frozen=True)
class JobAnalysisDraft:
    """Structured job analysis payload produced by deterministic helpers.

    Attributes:
        normalized_title: Canonically normalized role title.
        detected_language: Analysis language code.
        summary: Short deterministic summary of extracted requirements.
        requirements: Ordered requirement list.
    """

    normalized_title: str
    detected_language: str
    summary: str
    requirements: list[RequirementDraft]


def normalize_job_title(title: str) -> str:
    """Normalize the job title string.

    Args:
        title: Raw job title.

    Returns:
        Whitespace-normalized title.
    """

    return normalize_text(title)


def build_structured_job_analysis(
    *,
    title: str,
    description: str,
    detected_language: str,
) -> JobAnalysisDraft:
    """Build a deterministic structured analysis from job input text.

    Args:
        title: Job title.
        description: Raw job description.
        detected_language: Language code selected earlier in the flow.

    Returns:
        Structured job analysis draft.
    """

    normalized_title = normalize_job_title(title)
    candidate_lines = split_candidate_lines(description)
    requirements = extract_requirements(candidate_lines)
    summary = build_analysis_summary(requirements)

    return JobAnalysisDraft(
        normalized_title=normalized_title,
        detected_language=detected_language,
        summary=summary,
        requirements=requirements,
    )


def extract_requirements(lines: list[str]) -> list[RequirementDraft]:
    """Extract and classify requirements from candidate lines.

    Args:
        lines: Candidate requirement lines.

    Returns:
        Deduplicated and ranked requirements.
    """

    seen: set[str] = set()
    items: list[RequirementDraft] = []

    for index, line in enumerate(lines):
        normalized = normalize_text(line).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        must_have = classify_must_have(line)
        requirement_type = classify_requirement_type(line)
        priority_score = compute_priority_score(must_have=must_have, text=line)

        item = RequirementDraft(
            text=normalize_text(line),
            normalized_text=normalized,
            requirement_type=requirement_type,
            is_must_have=must_have,
            priority_score=priority_score,
            source_line_index=index,
        )
        items.append(item)

    return sorted(items, key=lambda entry: (-entry.priority_score, entry.source_line_index))


def classify_must_have(text: str) -> bool:
    """Classify whether a requirement appears mandatory.

    Args:
        text: Requirement candidate text.

    Returns:
        True when mandatory markers dominate the signal.
    """

    lowered = normalize_text(text).lower()
    if any(marker in lowered for marker in _NICE_TO_HAVE_MARKERS):
        return False
    return any(marker in lowered for marker in _MUST_HAVE_MARKERS)


def classify_requirement_type(text: str) -> str:
    """Determine requirement category based on deterministic markers.

    Args:
        text: Requirement candidate text.

    Returns:
        Category string suitable for filtering.
    """

    lowered = normalize_text(text).lower()

    if any(marker in lowered for marker in _SKILL_MARKERS):
        return "skill"
    if "year" in lowered or "jahre" in lowered or "experience" in lowered or "erfahrung" in lowered:
        return "experience"
    if "degree" in lowered or "bachelor" in lowered or "master" in lowered or "studium" in lowered:
        return "education"
    if "english" in lowered or "german" in lowered or "deutsch" in lowered:
        return "language"
    return "general"


def compute_priority_score(*, must_have: bool, text: str) -> int:
    """Compute deterministic requirement priority score.

    Args:
        must_have: Must-have classification result.
        text: Requirement candidate text.

    Returns:
        Priority score from 0 to 100.
    """

    lowered = normalize_text(text).lower()
    if must_have:
        return 90
    if any(marker in lowered for marker in _NICE_TO_HAVE_MARKERS):
        return 50
    return 70


def build_analysis_summary(requirements: list[RequirementDraft]) -> str:
    """Build a deterministic summary string for extracted requirements.

    Args:
        requirements: Requirement list.

    Returns:
        Summary text.
    """

    must_count = sum(1 for item in requirements if item.is_must_have)
    nice_count = sum(1 for item in requirements if not item.is_must_have)
    return f"Extracted {len(requirements)} requirements ({must_count} must-have, {nice_count} nice-to-have)."
