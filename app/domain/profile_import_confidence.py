"""Confidence scoring and review-policy helpers for profile import fields."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportReviewPolicy:
    """Configuration for confidence-driven review recommendations."""

    auto_approve_min_confidence: int = 94
    medium_confidence_min: int = 70
    auto_approve_sections: tuple[str, ...] = ("skill",)


DEFAULT_IMPORT_REVIEW_POLICY = ImportReviewPolicy()


def score_scalar_field_confidence(*, field_path: str, value: str) -> int:
    """Score confidence for a scalar extracted field.

    Args:
        field_path: Target scalar field path.
        value: Extracted scalar field value.

    Returns:
        Integer confidence score in range ``0..100``.
    """

    normalized = value.strip()
    if not normalized:
        return 0

    if field_path == "email":
        if _EMAIL_PATTERN.fullmatch(normalized):
            return 97
        return 25

    if field_path == "phone":
        digits = re.sub(r"\D", "", normalized)
        if 7 <= len(digits) <= 15:
            return 90
        return 35

    if field_path == "full_name":
        word_count = len(normalized.split())
        if 2 <= word_count <= 5 and not any(char.isdigit() for char in normalized):
            return 88
        return 45

    if field_path == "headline":
        if 6 <= len(normalized) <= 90:
            return 72
        return 48

    if field_path == "summary":
        if 20 <= len(normalized) <= 450:
            return 68
        return 40

    if field_path == "location":
        if 2 <= len(normalized) <= 80:
            return 60
        return 35

    return 50


def score_experience_field_confidence(*, field_name: str, value: str, description: str | None) -> int:
    """Score confidence for one extracted experience field.

    Args:
        field_name: Experience field name.
        value: Extracted experience field value.
        description: Optional source description context.

    Returns:
        Integer confidence score in range ``0..100``.
    """

    cleaned = value.strip()
    if not cleaned:
        return 0

    if field_name in {"start_date", "end_date"}:
        return 82 if _ISO_DATE_PATTERN.fullmatch(cleaned) else 25

    if field_name == "title":
        base = 70
        if _looks_like_narrative_sentence(cleaned):
            base -= 35
        if len(cleaned.split()) > 8:
            base -= 20
        return _clamp(base)

    if field_name == "company":
        base = 72
        if _looks_like_narrative_sentence(cleaned):
            base -= 30
        if len(cleaned.split()) > 7:
            base -= 20
        if "," in cleaned:
            base -= 10
        return _clamp(base)

    if field_name == "description":
        base = 58
        if description and cleaned == description:
            base += 8
        if len(cleaned) < 20:
            base -= 20
        return _clamp(base)

    return 50


def score_education_field_confidence(*, field_name: str, value: str) -> int:
    """Score confidence for one extracted education field."""

    cleaned = value.strip()
    if not cleaned:
        return 0

    if field_name in {"start_date", "end_date"}:
        return 80 if _ISO_DATE_PATTERN.fullmatch(cleaned) else 25

    if field_name == "degree":
        lowered = cleaned.lower()
        if any(marker in lowered for marker in _DEGREE_MARKERS):
            return 82
        return 54

    if field_name == "institution":
        if 2 <= len(cleaned) <= 90 and not _looks_like_narrative_sentence(cleaned):
            return 78
        return 45

    if field_name == "field_of_study":
        if 2 <= len(cleaned) <= 90:
            return 66
        return 40

    return 50


def score_skill_field_confidence(*, field_name: str, value: str) -> int:
    """Score confidence for one extracted skill field."""

    cleaned = value.strip()
    if not cleaned:
        return 0

    if field_name != "skill_name":
        return 45

    if 2 <= len(cleaned) <= 40 and not _looks_like_narrative_sentence(cleaned):
        return 92
    return 40


def recommend_review_decision(
    *,
    section_type: str,
    field_path: str,
    confidence_score: int,
    policy: ImportReviewPolicy = DEFAULT_IMPORT_REVIEW_POLICY,
) -> str:
    """Return review recommendation label for one field.

    Args:
        section_type: Field section type.
        field_path: Field path.
        confidence_score: Field confidence score.
        policy: Review-policy settings.

    Returns:
        Recommendation string ``approve`` or ``review``.
    """

    if (
        section_type in policy.auto_approve_sections
        and confidence_score >= policy.auto_approve_min_confidence
        and not _is_high_risk_field_path(field_path)
    ):
        return "approve"
    return "review"


def default_decision_status(
    *,
    section_type: str,
    field_path: str,
    confidence_score: int,
    policy: ImportReviewPolicy = DEFAULT_IMPORT_REVIEW_POLICY,
) -> str:
    """Return default decision status to persist for extracted fields."""

    recommendation = recommend_review_decision(
        section_type=section_type,
        field_path=field_path,
        confidence_score=confidence_score,
        policy=policy,
    )
    return "approved" if recommendation == "approve" else "pending"


def risk_level_for_field(*, field_path: str, section_type: str, confidence_score: int) -> str:
    """Return risk level label for extracted field review.

    Args:
        field_path: Field path.
        section_type: Section type.
        confidence_score: Confidence score.

    Returns:
        Risk level string ``low``, ``medium``, or ``high``.
    """

    if _is_high_risk_field_path(field_path) or section_type in {"experience", "education"}:
        if confidence_score < 80:
            return "high"
        return "medium"

    if confidence_score >= 90:
        return "low"
    if confidence_score >= 70:
        return "medium"
    return "high"


def _is_high_risk_field_path(field_path: str) -> bool:
    """Return whether field path should always be manually reviewed."""

    if field_path in {"full_name", "email", "phone", "headline", "summary"}:
        return True
    return field_path.startswith("experiences[") or field_path.startswith("educations[")


def _looks_like_narrative_sentence(value: str) -> bool:
    """Return whether value appears to be long narrative prose."""

    lowered = value.lower()
    if len(value) > 90:
        return True
    return any(token in lowered for token in (" delivering ", " currently ", " responsible", " project "))


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    """Clamp score into inclusive range."""

    return max(minimum, min(maximum, value))


_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_DEGREE_MARKERS = ("bachelor", "master", "msc", "bsc", "phd", "diplom", "mba")
