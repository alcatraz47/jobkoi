"""Unit tests for deterministic job analysis builder helpers."""

from __future__ import annotations

from app.domain.job_analysis import (
    build_structured_job_analysis,
    classify_must_have,
    classify_requirement_type,
)


def test_classify_must_have_prioritizes_nice_to_have_marker() -> None:
    """Nice-to-have phrases should override mandatory markers when both appear."""

    text = "Nice to have Python, must be familiar with Linux"
    assert classify_must_have(text) is False


def test_classify_requirement_type_detects_skill_language_and_experience() -> None:
    """Requirement type classifier should detect primary categories."""

    assert classify_requirement_type("Must have Python and SQL") == "skill"
    assert classify_requirement_type("3 years of experience in backend engineering") == "experience"
    assert classify_requirement_type("Fluent English and German required") == "language"


def test_build_structured_job_analysis_extracts_must_and_nice_requirements() -> None:
    """Analysis builder should return structured requirements and summary."""

    description = (
        "Must have Python and FastAPI experience. "
        "Nice to have Docker knowledge. "
        "Bachelor degree in Computer Science preferred."
    )
    analysis = build_structured_job_analysis(
        title="Backend Engineer",
        description=description,
        detected_language="en",
    )

    assert analysis.normalized_title == "Backend Engineer"
    assert analysis.detected_language == "en"
    assert len(analysis.requirements) == 3
    assert any(item.is_must_have for item in analysis.requirements)
    assert any(not item.is_must_have for item in analysis.requirements)
    assert analysis.summary.startswith("Extracted 3 requirements")
