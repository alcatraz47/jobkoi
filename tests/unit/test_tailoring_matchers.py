"""Unit tests for tailoring matchers and relevance scoring."""

from __future__ import annotations

from app.domain.tailoring_matchers import (
    build_requirement_keyword_set,
    compute_relevance_score,
    count_must_have_hits,
    keyword_match_score,
    skill_match_score,
)
from app.domain.tailoring_types import JobRequirementData


def test_skill_and_keyword_matching_scores_are_positive_for_overlap() -> None:
    """Matching helpers should score overlapping profile facts positively."""

    requirements = [
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
    ]
    keywords = build_requirement_keyword_set(requirements)

    assert skill_match_score("Python", keywords) > 0.0
    assert keyword_match_score("Built FastAPI services", keywords) > 0.0


def test_must_have_hits_and_relevance_scoring_are_deterministic() -> None:
    """Scoring helpers should return deterministic output for fixed inputs."""

    requirements = [
        JobRequirementData(
            id="req-1",
            text="Must have Python and SQL",
            requirement_type="skill",
            is_must_have=True,
            priority_score=90,
        ),
        JobRequirementData(
            id="req-2",
            text="Strong communication",
            requirement_type="general",
            is_must_have=False,
            priority_score=70,
        ),
    ]

    hits = count_must_have_hits("Developed Python APIs", requirements)
    score = compute_relevance_score(skill_score=1.0, keyword_score=0.5, must_have_hits=hits)

    assert hits == 1
    assert 0 <= score <= 100
    assert score == compute_relevance_score(skill_score=1.0, keyword_score=0.5, must_have_hits=hits)


def test_matching_handles_alias_terms_for_portal_requirements() -> None:
    """Matching should align common abbreviation/full-form skill variants."""

    requirements = [
        JobRequirementData(
            id="req-1",
            text="Natural Language Processing and Large Language Models experience",
            requirement_type="skill",
            is_must_have=True,
            priority_score=90,
        ),
        JobRequirementData(
            id="req-2",
            text="Experience with CI/CD and MLOps pipelines",
            requirement_type="skill",
            is_must_have=True,
            priority_score=85,
        ),
    ]
    keywords = build_requirement_keyword_set(requirements)

    assert skill_match_score("NLP", keywords) > 0.0
    assert skill_match_score("LLM", keywords) > 0.0
    assert skill_match_score("CI/CD", keywords) > 0.0
    assert keyword_match_score("Built MLOps platform", keywords) > 0.0

