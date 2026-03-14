"""Run profile import extraction quality evaluation against golden cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.profile_import_builders import build_imported_profile_from_text
from app.domain.profile_import_quality import ProfileImportQualityReport, evaluate_profile_import_quality
from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)


@dataclass(frozen=True)
class QualityCase:
    """One extraction quality test case loaded from dataset."""

    case_id: str
    language: str
    source_type: str
    source_locator: str
    input_text: str
    expected: ImportedProfileDraft


@dataclass(frozen=True)
class QualityCaseResult:
    """Evaluation output for one extraction quality case."""

    case_id: str
    source_type: str
    language: str
    report: ProfileImportQualityReport


def load_quality_cases(dataset_path: Path) -> list[QualityCase]:
    """Load extraction quality cases from JSON dataset.

    Args:
        dataset_path: Path to golden-case JSON file.

    Returns:
        Parsed quality cases.

    Raises:
        ValueError: If dataset format is invalid.
    """

    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    case_rows = payload.get("cases")
    if not isinstance(case_rows, list):
        raise ValueError("Quality dataset must include a 'cases' list.")

    cases: list[QualityCase] = []
    for row in case_rows:
        if not isinstance(row, dict):
            continue

        expected_payload = row.get("expected")
        if not isinstance(expected_payload, dict):
            raise ValueError(f"Case '{row.get('id', '-')}' is missing expected payload.")

        case = QualityCase(
            case_id=str(row.get("id", "")),
            language=str(row.get("language", "")),
            source_type=str(row.get("source_type", "")),
            source_locator=str(row.get("source_locator", "")),
            input_text=str(row.get("input_text", "")),
            expected=_imported_profile_from_dict(expected_payload),
        )
        if not case.case_id:
            raise ValueError("Quality case id cannot be empty.")
        cases.append(case)

    return cases


def evaluate_cases(cases: list[QualityCase]) -> list[QualityCaseResult]:
    """Evaluate all quality cases using current profile-import builders.

    Args:
        cases: Loaded quality cases.

    Returns:
        Evaluated case results.
    """

    results: list[QualityCaseResult] = []
    for case in cases:
        actual = build_imported_profile_from_text(
            text=case.input_text,
            source_locator=case.source_locator,
        )
        report = evaluate_profile_import_quality(expected=case.expected, actual=actual)
        results.append(
            QualityCaseResult(
                case_id=case.case_id,
                source_type=case.source_type,
                language=case.language,
                report=report,
            )
        )

    return results


def summarize_macro_f1(results: list[QualityCaseResult]) -> float:
    """Return mean macro-F1 across all evaluated cases."""

    if not results:
        return 0.0
    total = sum(item.report.macro_f1 for item in results)
    return round(total / len(results), 4)


def main() -> None:
    """Run quality report and print JSON summary."""

    dataset_path = Path("tests/quality/profile_import_goldens.json")
    cases = load_quality_cases(dataset_path)
    results = evaluate_cases(cases)

    output = {
        "dataset": str(dataset_path),
        "case_count": len(results),
        "macro_f1_mean": summarize_macro_f1(results),
        "cases": [
            {
                "id": item.case_id,
                "source_type": item.source_type,
                "language": item.language,
                "macro_f1": item.report.macro_f1,
                "scalar_f1": item.report.scalar_metrics.f1,
                "experience_f1": item.report.experience_metrics.f1,
                "education_f1": item.report.education_metrics.f1,
                "skill_f1": item.report.skill_metrics.f1,
            }
            for item in results
        ],
    }
    print(json.dumps(output, indent=2))



def _imported_profile_from_dict(payload: dict[str, Any]) -> ImportedProfileDraft:
    """Parse one imported-profile payload from JSON mapping."""

    experiences = _parse_experiences(payload.get("experiences"))
    educations = _parse_educations(payload.get("educations"))
    skills = _parse_skills(payload.get("skills"))

    return ImportedProfileDraft(
        full_name=_optional_text(payload.get("full_name")),
        email=_optional_text(payload.get("email")),
        phone=_optional_text(payload.get("phone")),
        location=_optional_text(payload.get("location")),
        headline=_optional_text(payload.get("headline")),
        summary=_optional_text(payload.get("summary")),
        experiences=experiences,
        educations=educations,
        skills=skills,
    )


def _parse_experiences(value: Any) -> list[ImportedExperienceDraft]:
    """Parse imported experience rows from JSON value."""

    if not isinstance(value, list):
        return []

    rows: list[ImportedExperienceDraft] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        company = _optional_text(item.get("company"))
        title = _optional_text(item.get("title"))
        if not company or not title:
            continue

        rows.append(
            ImportedExperienceDraft(
                company=company,
                title=title,
                start_date=_optional_text(item.get("start_date")),
                end_date=_optional_text(item.get("end_date")),
                description=_optional_text(item.get("description")),
                source_locator=_optional_text(item.get("source_locator")),
            )
        )

    return rows


def _parse_educations(value: Any) -> list[ImportedEducationDraft]:
    """Parse imported education rows from JSON value."""

    if not isinstance(value, list):
        return []

    rows: list[ImportedEducationDraft] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        institution = _optional_text(item.get("institution"))
        degree = _optional_text(item.get("degree"))
        if not institution or not degree:
            continue

        rows.append(
            ImportedEducationDraft(
                institution=institution,
                degree=degree,
                field_of_study=_optional_text(item.get("field_of_study")),
                start_date=_optional_text(item.get("start_date")),
                end_date=_optional_text(item.get("end_date")),
                source_locator=_optional_text(item.get("source_locator")),
            )
        )

    return rows


def _parse_skills(value: Any) -> list[ImportedSkillDraft]:
    """Parse imported skill rows from JSON value."""

    if not isinstance(value, list):
        return []

    rows: list[ImportedSkillDraft] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        skill_name = _optional_text(item.get("skill_name"))
        if not skill_name:
            continue

        rows.append(
            ImportedSkillDraft(
                skill_name=skill_name,
                level=_optional_text(item.get("level")),
                category=_optional_text(item.get("category")),
                source_locator=_optional_text(item.get("source_locator")),
            )
        )

    return rows


def _optional_text(value: Any) -> str | None:
    """Return stripped text or ``None`` for empty values."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    main()
