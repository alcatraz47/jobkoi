"""Unit tests for deterministic profile import adjudication helpers."""

from __future__ import annotations

from app.domain.profile_import_adjudication import adjudicate_profile_import_drafts
from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)


def test_adjudication_drops_contact_bundle_headline() -> None:
    """Contact-like headline from LLM should fallback to deterministic headline."""

    llm_draft = ImportedProfileDraft(
        headline="+49 123 456789 | arfan@example.com | Dortmund",
    )
    rule_draft = ImportedProfileDraft(
        headline="Senior Machine Learning Engineer",
    )

    result = adjudicate_profile_import_drafts(llm_draft=llm_draft, rule_draft=rule_draft)

    assert result.headline == "Senior Machine Learning Engineer"


def test_adjudication_replaces_education_like_location_with_rule_location() -> None:
    """Education-like LLM location should not override rule-based location."""

    llm_draft = ImportedProfileDraft(
        location="Master of Data Science, Carl von Ossietzky University Oldenburg",
    )
    rule_draft = ImportedProfileDraft(location="Dortmund, Germany")

    result = adjudicate_profile_import_drafts(llm_draft=llm_draft, rule_draft=rule_draft)

    assert result.location == "Dortmund, Germany"


def test_adjudication_merges_section_rows_with_llm_priority() -> None:
    """LLM rows should be kept first while rule rows backfill missing entries."""

    llm_draft = ImportedProfileDraft(
        experiences=[
            ImportedExperienceDraft(company="Fraunhofer IML", title="ML Engineer"),
        ],
        educations=[
            ImportedEducationDraft(institution="University A", degree="MSc Data Science"),
        ],
        skills=[
            ImportedSkillDraft(skill_name="Python"),
        ],
    )
    rule_draft = ImportedProfileDraft(
        experiences=[
            ImportedExperienceDraft(company="Fraunhofer IML", title="ML Engineer"),
            ImportedExperienceDraft(company="HT Ventures", title="AI Engineer"),
        ],
        educations=[
            ImportedEducationDraft(institution="University B", degree="BSc CS"),
        ],
        skills=[ImportedSkillDraft(skill_name="Python"), ImportedSkillDraft(skill_name="FastAPI")],
    )

    result = adjudicate_profile_import_drafts(llm_draft=llm_draft, rule_draft=rule_draft)

    assert len(result.experiences) == 2
    assert len(result.educations) == 2
    assert [item.skill_name for item in result.skills] == ["Python", "FastAPI"]
