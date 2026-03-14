"""Quality evaluation helpers for profile import extraction outputs."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)


@dataclass(frozen=True)
class FieldMatchResult:
    """Comparison result for one scalar profile field.

    Attributes:
        field_name: Scalar field name.
        expected: Expected field value.
        actual: Actual extracted field value.
        is_match: Whether normalized values match exactly.
    """

    field_name: str
    expected: str | None
    actual: str | None
    is_match: bool


@dataclass(frozen=True)
class SectionMetrics:
    """Precision/recall metrics for one extracted section."""

    expected_count: int
    predicted_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class ProfileImportQualityReport:
    """Aggregated quality report for one extracted profile draft."""

    scalar_results: tuple[FieldMatchResult, ...]
    scalar_metrics: SectionMetrics
    experience_metrics: SectionMetrics
    education_metrics: SectionMetrics
    skill_metrics: SectionMetrics
    macro_f1: float


def evaluate_profile_import_quality(
    *,
    expected: ImportedProfileDraft,
    actual: ImportedProfileDraft,
) -> ProfileImportQualityReport:
    """Evaluate extraction quality between expected and actual drafts.

    Args:
        expected: Golden expected profile draft.
        actual: Extracted profile draft to score.

    Returns:
        Structured quality report with per-section metrics.
    """

    scalar_results = _evaluate_scalar_fields(expected=expected, actual=actual)
    scalar_metrics = _scalar_results_to_metrics(scalar_results)

    expected_experience = _experience_keys(expected.experiences)
    actual_experience = _experience_keys(actual.experiences)
    experience_metrics = _set_metrics(expected_items=expected_experience, predicted_items=actual_experience)

    expected_education = _education_keys(expected.educations)
    actual_education = _education_keys(actual.educations)
    education_metrics = _set_metrics(expected_items=expected_education, predicted_items=actual_education)

    expected_skill = _skill_keys(expected.skills)
    actual_skill = _skill_keys(actual.skills)
    skill_metrics = _set_metrics(expected_items=expected_skill, predicted_items=actual_skill)

    macro_f1 = (
        scalar_metrics.f1
        + experience_metrics.f1
        + education_metrics.f1
        + skill_metrics.f1
    ) / 4.0

    return ProfileImportQualityReport(
        scalar_results=scalar_results,
        scalar_metrics=scalar_metrics,
        experience_metrics=experience_metrics,
        education_metrics=education_metrics,
        skill_metrics=skill_metrics,
        macro_f1=round(macro_f1, 4),
    )


def _evaluate_scalar_fields(
    *,
    expected: ImportedProfileDraft,
    actual: ImportedProfileDraft,
) -> tuple[FieldMatchResult, ...]:
    """Evaluate scalar-field exact matches after normalization."""

    scalar_names = (
        "full_name",
        "email",
        "phone",
        "location",
        "headline",
        "summary",
    )

    results: list[FieldMatchResult] = []
    for field_name in scalar_names:
        expected_value = getattr(expected, field_name)
        actual_value = getattr(actual, field_name)
        is_match = _normalize_value(expected_value) == _normalize_value(actual_value)
        results.append(
            FieldMatchResult(
                field_name=field_name,
                expected=expected_value,
                actual=actual_value,
                is_match=is_match,
            )
        )

    return tuple(results)


def _scalar_results_to_metrics(results: tuple[FieldMatchResult, ...]) -> SectionMetrics:
    """Convert scalar-field comparisons to precision/recall metrics."""

    expected_count = 0
    predicted_count = 0
    true_positives = 0

    for result in results:
        expected_normalized = _normalize_value(result.expected)
        actual_normalized = _normalize_value(result.actual)

        has_expected = bool(expected_normalized)
        has_predicted = bool(actual_normalized)

        if has_expected:
            expected_count += 1
        if has_predicted:
            predicted_count += 1

        if has_expected and has_predicted and result.is_match:
            true_positives += 1

    false_positives = max(predicted_count - true_positives, 0)
    false_negatives = max(expected_count - true_positives, 0)

    return _build_metrics(
        expected_count=expected_count,
        predicted_count=predicted_count,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def _set_metrics(*, expected_items: set[str], predicted_items: set[str]) -> SectionMetrics:
    """Compute set-based precision/recall metrics."""

    true_positives = len(expected_items & predicted_items)
    false_positives = len(predicted_items - expected_items)
    false_negatives = len(expected_items - predicted_items)

    return _build_metrics(
        expected_count=len(expected_items),
        predicted_count=len(predicted_items),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def _build_metrics(
    *,
    expected_count: int,
    predicted_count: int,
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> SectionMetrics:
    """Build rounded metrics from confusion counts."""

    if expected_count == 0 and predicted_count == 0:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    else:
        precision = _safe_divide(true_positives, true_positives + false_positives)
        recall = _safe_divide(true_positives, true_positives + false_negatives)
        f1 = _safe_divide(2 * precision * recall, precision + recall)

    return SectionMetrics(
        expected_count=expected_count,
        predicted_count=predicted_count,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def _experience_keys(items: list[ImportedExperienceDraft]) -> set[str]:
    """Return normalized comparison keys for experience rows."""

    keys: set[str] = set()
    for item in items:
        title = _normalize_value(item.title)
        company = _normalize_value(item.company)
        if not title or not company:
            continue
        keys.add(f"{title}|{company}")
    return keys


def _education_keys(items: list[ImportedEducationDraft]) -> set[str]:
    """Return normalized comparison keys for education rows."""

    keys: set[str] = set()
    for item in items:
        degree = _normalize_value(item.degree)
        institution = _normalize_value(item.institution)
        if not degree or not institution:
            continue
        keys.add(f"{degree}|{institution}")
    return keys


def _skill_keys(items: list[ImportedSkillDraft]) -> set[str]:
    """Return normalized comparison keys for skill rows."""

    keys: set[str] = set()
    for item in items:
        normalized = _normalize_value(item.skill_name)
        if not normalized:
            continue
        keys.add(normalized)
    return keys


def _normalize_value(value: str | None) -> str:
    """Normalize one extracted value for deterministic comparisons."""

    if value is None:
        return ""

    cleaned = " ".join(value.strip().lower().split())
    return cleaned.strip(".,;:|-_")


def _safe_divide(numerator: float, denominator: float) -> float:
    """Return zero-safe division result."""

    if denominator == 0:
        return 0.0
    return numerator / denominator
