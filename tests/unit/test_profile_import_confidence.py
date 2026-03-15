"""Unit tests for profile import confidence and review policy helpers."""

from __future__ import annotations

from app.domain.profile_import_confidence import (
    default_decision_status,
    recommend_review_decision,
    risk_level_for_field,
    score_experience_field_confidence,
    score_scalar_field_confidence,
    score_skill_field_confidence,
)


def test_score_scalar_field_confidence_email_high_for_valid_value() -> None:
    """Email confidence should be high when value is well-formed."""

    assert score_scalar_field_confidence(field_path="email", value="arfan@example.com") >= 90


def test_score_experience_field_confidence_penalizes_narrative_company() -> None:
    """Narrative company values should produce low confidence."""

    score = score_experience_field_confidence(
        field_name="company",
        value="Fraunhofer IML delivering computer vision solutions",
        description=None,
    )

    assert score < 60


def test_score_skill_field_confidence_high_for_compact_skill_name() -> None:
    """Skill confidence should be high for compact, non-narrative names."""

    assert score_skill_field_confidence(field_name="skill_name", value="Python") >= 90


def test_default_decision_status_auto_approves_only_low_risk_high_confidence() -> None:
    """Default decision should auto-approve only eligible high-confidence fields."""

    assert default_decision_status(
        section_type="skill",
        field_path="skills[0].skill_name",
        confidence_score=96,
    ) == "approved"

    assert default_decision_status(
        section_type="experience",
        field_path="experiences[0].title",
        confidence_score=96,
    ) == "pending"


def test_recommend_review_decision_returns_review_for_high_risk_fields() -> None:
    """High-risk fields should still require review recommendation."""

    recommendation = recommend_review_decision(
        section_type="personal",
        field_path="email",
        confidence_score=99,
    )
    assert recommendation == "review"


def test_risk_level_for_field_marks_experience_as_high_when_confidence_low() -> None:
    """Experience rows should be high risk at low confidence."""

    risk = risk_level_for_field(
        field_path="experiences[0].company",
        section_type="experience",
        confidence_score=52,
    )
    assert risk == "high"


def test_score_scalar_field_confidence_penalizes_contact_bundle_as_headline() -> None:
    """Headline confidence should drop when value looks like contact/location data."""

    score = score_scalar_field_confidence(
        field_path="headline",
        value="+49 176 32925096 | Dortmund, Germany",
    )

    assert score < 40


def test_score_scalar_field_confidence_penalizes_education_like_location() -> None:
    """Location confidence should drop when value looks like education content."""

    score = score_scalar_field_confidence(
        field_path="location",
        value="Master of Data Science, Carl von Ossietzky University Oldenburg",
    )

    assert score < 40


def test_score_experience_field_confidence_penalizes_status_as_company() -> None:
    """Company confidence should be very low for temporal-status values."""

    score = score_experience_field_confidence(
        field_name="company",
        value="Present",
        description=None,
    )

    assert score < 30
