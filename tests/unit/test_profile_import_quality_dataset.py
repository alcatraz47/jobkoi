"""Tests for profile import quality golden dataset integrity."""

from __future__ import annotations

import json
from pathlib import Path


def test_profile_import_quality_dataset_has_minimum_case_count() -> None:
    """Golden dataset should contain enough cases for stable scoring."""

    payload = _load_dataset()
    cases = payload.get("cases")
    assert isinstance(cases, list)
    assert len(cases) >= 30


def test_profile_import_quality_dataset_has_unique_ids() -> None:
    """Golden dataset case identifiers should be unique."""

    payload = _load_dataset()
    ids = [str(item.get("id", "")) for item in payload["cases"] if isinstance(item, dict)]
    assert all(case_id for case_id in ids)
    assert len(ids) == len(set(ids))


def test_profile_import_quality_dataset_covers_languages_and_source_types() -> None:
    """Golden dataset should cover EN/DE and both source types."""

    payload = _load_dataset()
    languages = set()
    source_types = set()
    for item in payload["cases"]:
        if not isinstance(item, dict):
            continue
        languages.add(str(item.get("language", "")))
        source_types.add(str(item.get("source_type", "")))

    assert {"en", "de"}.issubset(languages)
    assert {"cv_document", "portfolio_website"}.issubset(source_types)


def _load_dataset() -> dict[str, object]:
    """Load profile import golden dataset as a dictionary."""

    dataset_path = Path("tests/quality/profile_import_goldens.json")
    return json.loads(dataset_path.read_text(encoding="utf-8"))
