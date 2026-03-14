"""Unit tests for tailoring plan and snapshot builders."""

from __future__ import annotations

import pytest

from app.domain.tailoring_builders import build_profile_snapshot, build_tailoring_plan
from app.domain.tailoring_guards import InventedClaimError, validate_rewrites_against_selected_facts
from app.domain.tailoring_types import (
    JobAnalysisData,
    JobRequirementData,
    ProfileEducationFact,
    ProfileExperienceFact,
    ProfileSkillFact,
    ProfileVersionData,
)


def build_profile_data() -> ProfileVersionData:
    """Build deterministic profile data fixture.

    Returns:
        Profile version data for unit tests.
    """

    return ProfileVersionData(
        id="pv-1",
        full_name="Arfan Example",
        email="arfan@example.com",
        phone="+49 123",
        location="Berlin",
        headline="Backend Engineer",
        summary="Python engineer with API experience.",
        experiences=[
            ProfileExperienceFact(
                id="exp-1",
                company="Example GmbH",
                title="Software Engineer",
                start_date=None,
                end_date=None,
                description="Built Python and FastAPI services for 3 years.",
            ),
            ProfileExperienceFact(
                id="exp-2",
                company="Other GmbH",
                title="Developer",
                start_date=None,
                end_date=None,
                description="Worked on frontend applications.",
            ),
        ],
        educations=[
            ProfileEducationFact(
                id="edu-1",
                institution="TU Example",
                degree="MSc",
                field_of_study="Computer Science",
                start_date=None,
                end_date=None,
            )
        ],
        skills=[
            ProfileSkillFact(id="skill-1", skill_name="Python", level="advanced", category="programming"),
            ProfileSkillFact(id="skill-2", skill_name="FastAPI", level="advanced", category="backend"),
            ProfileSkillFact(id="skill-3", skill_name="React", level="intermediate", category="frontend"),
        ],
    )


def build_analysis_data() -> JobAnalysisData:
    """Build deterministic job analysis fixture.

    Returns:
        Job analysis data for unit tests.
    """

    return JobAnalysisData(
        id="analysis-1",
        detected_language="en",
        requirements=[
            JobRequirementData(
                id="req-1",
                text="Must have Python and FastAPI experience",
                requirement_type="skill",
                is_must_have=True,
                priority_score=90,
            ),
            JobRequirementData(
                id="req-2",
                text="Nice to have Docker knowledge",
                requirement_type="skill",
                is_must_have=False,
                priority_score=50,
            ),
        ],
    )


def test_build_tailoring_plan_selects_relevant_experience_and_skills() -> None:
    """Plan builder should deterministically select the most relevant facts."""

    plan = build_tailoring_plan(
        profile=build_profile_data(),
        analysis=build_analysis_data(),
        target_language="en",
        max_experiences=1,
        max_skills=2,
        max_educations=1,
    )

    selected = [item for item in plan.facts if item.is_selected]
    selected_keys = {item.fact_key for item in selected}

    assert "experience:exp-1" in selected_keys
    assert "skill:skill-1" in selected_keys
    assert plan.target_language == "en"


def test_build_profile_snapshot_applies_valid_rewrite_for_selected_fact() -> None:
    """Snapshot builder should apply rewrite text only for selected facts."""

    profile = build_profile_data()
    plan = build_tailoring_plan(
        profile=profile,
        analysis=build_analysis_data(),
        target_language="en",
        max_experiences=1,
        max_skills=2,
        max_educations=1,
    )

    selected_map = {fact.fact_key: fact.text for fact in plan.facts if fact.is_selected}
    rewrites = {"experience:exp-1": "Built Python and FastAPI services for 3 years and mentored peers."}

    validate_rewrites_against_selected_facts(selected_fact_texts=selected_map, rewrites=rewrites)
    snapshot = build_profile_snapshot(profile=profile, plan=plan, rewrites=rewrites)

    assert len(snapshot.experiences) == 1
    assert snapshot.experiences[0].description == rewrites["experience:exp-1"]


def test_factual_guard_rejects_invented_numeric_claims() -> None:
    """Factual guard should reject rewrites introducing unsupported numbers."""

    selected = {"experience:exp-1": "Built Python and FastAPI services for 3 years."}
    rewrites = {"experience:exp-1": "Built Python and FastAPI services for 5 years."}

    with pytest.raises(InventedClaimError):
        validate_rewrites_against_selected_facts(selected_fact_texts=selected, rewrites=rewrites)
