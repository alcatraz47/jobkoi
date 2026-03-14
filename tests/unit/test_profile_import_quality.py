"""Unit tests for profile import extraction quality scoring helpers."""

from __future__ import annotations

from app.domain.profile_import_quality import evaluate_profile_import_quality
from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)


def test_evaluate_profile_import_quality_perfect_match_scores_one() -> None:
    """Perfect extraction should produce unit macro-F1."""

    expected = ImportedProfileDraft(
        full_name="Arfan Example",
        email="arfan@example.com",
        phone="+49 176 1234567",
        headline="Backend Engineer",
        experiences=[ImportedExperienceDraft(company="Example GmbH", title="Engineer")],
        educations=[ImportedEducationDraft(institution="TU Berlin", degree="MSc Computer Science")],
        skills=[ImportedSkillDraft(skill_name="Python")],
    )

    report = evaluate_profile_import_quality(expected=expected, actual=expected)

    assert report.scalar_metrics.f1 == 1.0
    assert report.experience_metrics.f1 == 1.0
    assert report.education_metrics.f1 == 1.0
    assert report.skill_metrics.f1 == 1.0
    assert report.macro_f1 == 1.0


def test_evaluate_profile_import_quality_counts_false_positives_and_negatives() -> None:
    """Mismatched extraction should report precision and recall penalties."""

    expected = ImportedProfileDraft(
        full_name="Arfan Example",
        email="arfan@example.com",
        experiences=[ImportedExperienceDraft(company="Example GmbH", title="Engineer")],
        skills=[ImportedSkillDraft(skill_name="Python")],
    )
    actual = ImportedProfileDraft(
        full_name="Arfan Example",
        email="wrong@example.com",
        experiences=[ImportedExperienceDraft(company="Another GmbH", title="Engineer")],
        skills=[ImportedSkillDraft(skill_name="Python"), ImportedSkillDraft(skill_name="Docker")],
    )

    report = evaluate_profile_import_quality(expected=expected, actual=actual)

    assert report.scalar_metrics.true_positives == 1
    assert report.scalar_metrics.false_positives >= 1
    assert report.scalar_metrics.false_negatives >= 1

    assert report.experience_metrics.true_positives == 0
    assert report.experience_metrics.false_positives == 1
    assert report.experience_metrics.false_negatives == 1

    assert report.skill_metrics.true_positives == 1
    assert report.skill_metrics.false_positives == 1
    assert report.skill_metrics.false_negatives == 0


def test_evaluate_profile_import_quality_empty_section_scores_full_credit() -> None:
    """Empty expected and predicted sections should count as perfect match."""

    expected = ImportedProfileDraft(full_name="Arfan Example")
    actual = ImportedProfileDraft(full_name="Arfan Example")

    report = evaluate_profile_import_quality(expected=expected, actual=actual)

    assert report.education_metrics.f1 == 1.0
    assert report.experience_metrics.f1 == 1.0
    assert report.skill_metrics.f1 == 1.0
