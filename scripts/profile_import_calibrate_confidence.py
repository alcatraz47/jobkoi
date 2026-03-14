"""Calibrate profile import confidence thresholds against golden extraction cases."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.profile_import_builders import (  # noqa: E402
    build_imported_profile_from_text,
    flatten_imported_profile_to_fields,
)
from app.domain.profile_import_types import ImportFieldDraft, ImportedProfileDraft  # noqa: E402
from scripts.profile_import_quality_report import load_quality_cases  # noqa: E402

_INDEXED_PATH_PATTERN = re.compile(r"^(?P<section>[a-z_]+)\[(?P<index>\d+)]\.(?P<field>[a-z_]+)$")


@dataclass(frozen=True)
class ConfidenceObservation:
    """One confidence observation labeled as correct/incorrect."""

    section: str
    confidence: int
    is_correct: bool


@dataclass(frozen=True)
class ThresholdMetrics:
    """Precision/recall metrics for one confidence threshold."""

    threshold: int
    precision: float
    recall: float
    f1: float
    selected_count: int


def main() -> None:
    """Run confidence calibration and print JSON summary."""

    dataset_path = Path("tests/quality/profile_import_goldens.json")
    cases = load_quality_cases(dataset_path)

    observations: list[ConfidenceObservation] = []
    for case in cases:
        actual = build_imported_profile_from_text(text=case.input_text, source_locator=case.source_locator)
        rows = flatten_imported_profile_to_fields(actual)
        observations.extend(_label_case_rows(rows=rows, expected=case.expected))

    by_section = _group_observations_by_section(observations)
    section_payload: dict[str, object] = {}
    for section, rows in by_section.items():
        curve = [_threshold_metrics(rows, threshold) for threshold in range(50, 101)]
        recommended = _pick_threshold(curve)
        section_payload[section] = {
            "observation_count": len(rows),
            "recommended_auto_approve_threshold": recommended.threshold,
            "precision": recommended.precision,
            "recall": recommended.recall,
            "f1": recommended.f1,
            "selected_count": recommended.selected_count,
        }

    output = {
        "dataset": str(dataset_path),
        "observation_count": len(observations),
        "sections": section_payload,
    }
    print(json.dumps(output, indent=2))


def _label_case_rows(
    *,
    rows: list[ImportFieldDraft],
    expected: ImportedProfileDraft,
) -> list[ConfidenceObservation]:
    """Label extracted field rows as correct or incorrect against expected draft."""

    observations: list[ConfidenceObservation] = []

    expected_scalar = {
        "full_name": _normalize(expected.full_name),
        "email": _normalize(expected.email),
        "phone": _normalize(expected.phone),
        "location": _normalize(expected.location),
        "headline": _normalize(expected.headline),
        "summary": _normalize(expected.summary),
    }
    expected_experience_titles = {_normalize(item.title) for item in expected.experiences}
    expected_experience_companies = {_normalize(item.company) for item in expected.experiences}
    expected_education_degrees = {_normalize(item.degree) for item in expected.educations}
    expected_education_institutions = {_normalize(item.institution) for item in expected.educations}
    expected_skills = {_normalize(item.skill_name) for item in expected.skills}

    for row in rows:
        section = row.section_type
        normalized_value = _normalize(row.suggested_value)
        if not normalized_value:
            continue

        is_correct: bool | None = None

        if row.field_path in expected_scalar:
            expected_value = expected_scalar[row.field_path]
            if not expected_value:
                continue
            is_correct = normalized_value == expected_value

        parsed_path = _parse_indexed_field_path(row.field_path)
        if parsed_path is not None:
            parsed_section, _, field_name = parsed_path
            if parsed_section == "experiences":
                if field_name == "title":
                    is_correct = normalized_value in expected_experience_titles
                elif field_name == "company":
                    is_correct = normalized_value in expected_experience_companies
                else:
                    continue
            elif parsed_section == "educations":
                if field_name == "degree":
                    is_correct = normalized_value in expected_education_degrees
                elif field_name == "institution":
                    is_correct = normalized_value in expected_education_institutions
                else:
                    continue
            elif parsed_section == "skills":
                if field_name == "skill_name":
                    is_correct = normalized_value in expected_skills
                else:
                    continue

        if is_correct is None:
            continue

        observations.append(
            ConfidenceObservation(
                section=section,
                confidence=int(row.confidence_score),
                is_correct=is_correct,
            )
        )

    return observations


def _group_observations_by_section(
    observations: list[ConfidenceObservation],
) -> dict[str, list[ConfidenceObservation]]:
    """Group confidence observations by section type."""

    grouped: dict[str, list[ConfidenceObservation]] = {}
    for item in observations:
        grouped.setdefault(item.section, []).append(item)
    return grouped


def _threshold_metrics(
    rows: list[ConfidenceObservation],
    threshold: int,
) -> ThresholdMetrics:
    """Compute precision/recall metrics at one threshold."""

    positives = [row for row in rows if row.is_correct]
    selected = [row for row in rows if row.confidence >= threshold]
    selected_true = [row for row in selected if row.is_correct]

    precision = _safe_divide(len(selected_true), len(selected))
    recall = _safe_divide(len(selected_true), len(positives))
    f1 = _safe_divide(2 * precision * recall, precision + recall)

    return ThresholdMetrics(
        threshold=threshold,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        selected_count=len(selected),
    )


def _pick_threshold(curve: list[ThresholdMetrics]) -> ThresholdMetrics:
    """Pick threshold with high precision and strongest recall."""

    if not curve:
        return ThresholdMetrics(threshold=100, precision=0.0, recall=0.0, f1=0.0, selected_count=0)

    precision_target = 0.95
    candidates = [item for item in curve if item.precision >= precision_target and item.selected_count > 0]
    if candidates:
        return max(candidates, key=lambda item: (item.recall, item.f1, -item.threshold))

    return max(curve, key=lambda item: (item.f1, item.precision, item.recall))


def _parse_indexed_field_path(field_path: str) -> tuple[str, int, str] | None:
    """Parse indexed field path into section, index, field name."""

    match = _INDEXED_PATH_PATTERN.match(field_path)
    if match is None:
        return None

    return (
        match.group("section"),
        int(match.group("index")),
        match.group("field"),
    )


def _normalize(value: str | None) -> str:
    """Normalize values for deterministic matching."""

    if value is None:
        return ""
    lowered = " ".join(value.strip().lower().split())
    return lowered.strip(".,;:|-_")


def _safe_divide(numerator: float, denominator: float) -> float:
    """Return zero-safe division result."""

    if denominator == 0:
        return 0.0
    return numerator / denominator


if __name__ == "__main__":
    main()
