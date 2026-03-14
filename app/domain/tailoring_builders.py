"""Pure builders for tailoring plans and profile snapshots."""

from __future__ import annotations

from app.domain.job_text import normalize_text
from app.domain.tailoring_matchers import (
    build_requirement_keyword_set,
    compute_relevance_score,
    count_must_have_hits,
    keyword_match_score,
    skill_match_score,
)
from app.domain.tailoring_types import (
    JobAnalysisData,
    JobRequirementData,
    ProfileSnapshotDraft,
    ProfileVersionData,
    SnapshotEducationDraft,
    SnapshotExperienceDraft,
    SnapshotSkillDraft,
    TailoringPlanDraft,
    TailoringPlanFactDraft,
)


def build_tailoring_plan(
    *,
    profile: ProfileVersionData,
    analysis: JobAnalysisData,
    target_language: str,
    max_experiences: int,
    max_skills: int,
    max_educations: int,
) -> TailoringPlanDraft:
    """Build a deterministic tailoring plan from profile and job analysis data.

    Args:
        profile: Profile version data.
        analysis: Structured job analysis.
        target_language: Desired output language code.
        max_experiences: Maximum selected experience facts.
        max_skills: Maximum selected skill facts.
        max_educations: Maximum selected education facts.

    Returns:
        Tailoring plan draft with scored facts and selection flags.
    """

    requirement_keywords = build_requirement_keyword_set(analysis.requirements)
    facts = _build_plan_facts(
        profile=profile,
        requirements=analysis.requirements,
        requirement_keywords=requirement_keywords,
    )
    selected_keys = _select_fact_keys(
        facts=facts,
        max_experiences=max_experiences,
        max_skills=max_skills,
        max_educations=max_educations,
    )
    selected_facts = _mark_selected_facts(facts=facts, selected_keys=selected_keys)
    summary = _build_plan_summary(
        profile_version_id=profile.id,
        analysis_id=analysis.id,
        selected_count=sum(1 for fact in selected_facts if fact.is_selected),
    )

    return TailoringPlanDraft(
        profile_version_id=profile.id,
        job_analysis_id=analysis.id,
        target_language=target_language,
        summary=summary,
        facts=selected_facts,
    )


def build_profile_snapshot(
    *,
    profile: ProfileVersionData,
    plan: TailoringPlanDraft,
    rewrites: dict[str, str],
) -> ProfileSnapshotDraft:
    """Build a tailored profile snapshot from selected plan facts.

    Args:
        profile: Source profile version data.
        plan: Persisted or drafted tailoring plan.
        rewrites: Optional fact-key rewrite text mapping.

    Returns:
        Tailored immutable snapshot draft.
    """

    selected_facts = _selected_facts_map(plan)
    headline = _resolve_rewritten_text(
        fact_key="profile:headline",
        default_text=profile.headline,
        selected_facts=selected_facts,
        rewrites=rewrites,
    )
    summary = _resolve_rewritten_text(
        fact_key="profile:summary",
        default_text=profile.summary,
        selected_facts=selected_facts,
        rewrites=rewrites,
    )

    return ProfileSnapshotDraft(
        profile_version_id=profile.id,
        target_language=plan.target_language,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        headline=headline,
        summary=summary,
        experiences=_build_snapshot_experiences(
            profile=profile,
            selected_facts=selected_facts,
            rewrites=rewrites,
        ),
        educations=_build_snapshot_educations(
            profile=profile,
            selected_facts=selected_facts,
        ),
        skills=_build_snapshot_skills(
            profile=profile,
            selected_facts=selected_facts,
            rewrites=rewrites,
        ),
    )


def _build_plan_facts(
    *,
    profile: ProfileVersionData,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
) -> list[TailoringPlanFactDraft]:
    """Build scored plan facts from profile sections."""

    facts: list[TailoringPlanFactDraft] = []
    facts.extend(
        _build_profile_header_facts(
            profile=profile,
            requirements=requirements,
            requirement_keywords=requirement_keywords,
        )
    )
    facts.extend(
        _build_experience_facts(
            profile=profile,
            requirements=requirements,
            requirement_keywords=requirement_keywords,
        )
    )
    facts.extend(
        _build_education_facts(
            profile=profile,
            requirements=requirements,
            requirement_keywords=requirement_keywords,
        )
    )
    facts.extend(
        _build_skill_facts(
            profile=profile,
            requirements=requirements,
            requirement_keywords=requirement_keywords,
        )
    )
    return facts


def _build_profile_header_facts(
    *,
    profile: ProfileVersionData,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
) -> list[TailoringPlanFactDraft]:
    """Build headline and summary facts when source text is available."""

    facts: list[TailoringPlanFactDraft] = []
    if profile.headline:
        facts.append(
            _build_fact(
                fact_key="profile:headline",
                fact_type="headline",
                source_entity_id=None,
                text=profile.headline,
                requirements=requirements,
                requirement_keywords=requirement_keywords,
                force_selected=False,
            )
        )
    if profile.summary:
        facts.append(
            _build_fact(
                fact_key="profile:summary",
                fact_type="summary",
                source_entity_id=None,
                text=profile.summary,
                requirements=requirements,
                requirement_keywords=requirement_keywords,
                force_selected=False,
            )
        )
    return facts


def _build_experience_facts(
    *,
    profile: ProfileVersionData,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
) -> list[TailoringPlanFactDraft]:
    """Build scored facts from profile experience rows."""

    facts: list[TailoringPlanFactDraft] = []
    for experience in profile.experiences:
        fact_text = normalize_text(f"{experience.title} at {experience.company} {experience.description or ''}")
        facts.append(
            _build_fact(
                fact_key=f"experience:{experience.id}",
                fact_type="experience",
                source_entity_id=experience.id,
                text=fact_text,
                requirements=requirements,
                requirement_keywords=requirement_keywords,
                force_selected=False,
            )
        )
    return facts


def _build_education_facts(
    *,
    profile: ProfileVersionData,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
) -> list[TailoringPlanFactDraft]:
    """Build scored facts from profile education rows."""

    facts: list[TailoringPlanFactDraft] = []
    for education in profile.educations:
        fact_text = normalize_text(f"{education.degree} at {education.institution} {education.field_of_study or ''}")
        facts.append(
            _build_fact(
                fact_key=f"education:{education.id}",
                fact_type="education",
                source_entity_id=education.id,
                text=fact_text,
                requirements=requirements,
                requirement_keywords=requirement_keywords,
                force_selected=False,
            )
        )
    return facts


def _build_skill_facts(
    *,
    profile: ProfileVersionData,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
) -> list[TailoringPlanFactDraft]:
    """Build scored facts from profile skill rows."""

    facts: list[TailoringPlanFactDraft] = []
    for skill in profile.skills:
        fact_text = normalize_text(f"{skill.skill_name} {skill.level or ''} {skill.category or ''}")
        facts.append(
            _build_fact(
                fact_key=f"skill:{skill.id}",
                fact_type="skill",
                source_entity_id=skill.id,
                text=fact_text,
                requirements=requirements,
                requirement_keywords=requirement_keywords,
                force_selected=False,
                skill_name=skill.skill_name,
            )
        )
    return facts


def _mark_selected_facts(
    *,
    facts: list[TailoringPlanFactDraft],
    selected_keys: set[str],
) -> list[TailoringPlanFactDraft]:
    """Return fact list with deterministic selection annotations."""

    return [
        TailoringPlanFactDraft(
            fact_key=fact.fact_key,
            fact_type=fact.fact_type,
            source_entity_id=fact.source_entity_id,
            text=fact.text,
            relevance_score=fact.relevance_score,
            is_selected=fact.fact_key in selected_keys,
            selection_reason=_build_selection_reason(
                relevance_score=fact.relevance_score,
                selected=fact.fact_key in selected_keys,
            ),
        )
        for fact in facts
    ]


def _build_plan_summary(*, profile_version_id: str, analysis_id: str, selected_count: int) -> str:
    """Build deterministic plan summary text."""

    return (
        f"Selected {selected_count} facts for tailoring from profile version {profile_version_id} "
        f"against analysis {analysis_id}."
    )


def _selected_facts_map(plan: TailoringPlanDraft) -> dict[str, TailoringPlanFactDraft]:
    """Return selected facts keyed by stable fact key."""

    return {fact.fact_key: fact for fact in plan.facts if fact.is_selected}


def _build_snapshot_experiences(
    *,
    profile: ProfileVersionData,
    selected_facts: dict[str, TailoringPlanFactDraft],
    rewrites: dict[str, str],
) -> list[SnapshotExperienceDraft]:
    """Build snapshot experience rows from selected plan facts."""

    entries: list[SnapshotExperienceDraft] = []
    for experience in profile.experiences:
        fact_key = f"experience:{experience.id}"
        selected_fact = selected_facts.get(fact_key)
        if selected_fact is None:
            continue

        rewritten_text = rewrites.get(fact_key)
        description = rewritten_text if rewritten_text is not None else experience.description
        entries.append(
            SnapshotExperienceDraft(
                source_experience_id=experience.id,
                company=experience.company,
                title=experience.title,
                start_date=experience.start_date,
                end_date=experience.end_date,
                description=description,
                relevance_score=selected_fact.relevance_score,
            )
        )
    return entries


def _build_snapshot_educations(
    *,
    profile: ProfileVersionData,
    selected_facts: dict[str, TailoringPlanFactDraft],
) -> list[SnapshotEducationDraft]:
    """Build snapshot education rows from selected plan facts."""

    entries: list[SnapshotEducationDraft] = []
    for education in profile.educations:
        fact_key = f"education:{education.id}"
        selected_fact = selected_facts.get(fact_key)
        if selected_fact is None:
            continue

        entries.append(
            SnapshotEducationDraft(
                source_education_id=education.id,
                institution=education.institution,
                degree=education.degree,
                field_of_study=education.field_of_study,
                start_date=education.start_date,
                end_date=education.end_date,
                relevance_score=selected_fact.relevance_score,
            )
        )
    return entries


def _build_snapshot_skills(
    *,
    profile: ProfileVersionData,
    selected_facts: dict[str, TailoringPlanFactDraft],
    rewrites: dict[str, str],
) -> list[SnapshotSkillDraft]:
    """Build snapshot skill rows from selected plan facts."""

    entries: list[SnapshotSkillDraft] = []
    for skill in profile.skills:
        fact_key = f"skill:{skill.id}"
        selected_fact = selected_facts.get(fact_key)
        if selected_fact is None:
            continue

        rewritten_skill_text = rewrites.get(fact_key)
        if rewritten_skill_text is not None:
            skill_name = rewritten_skill_text
            level = None
            category = None
        else:
            skill_name = skill.skill_name
            level = skill.level
            category = skill.category

        entries.append(
            SnapshotSkillDraft(
                source_skill_id=skill.id,
                skill_name=skill_name,
                level=level,
                category=category,
                relevance_score=selected_fact.relevance_score,
            )
        )
    return entries


def _build_fact(
    *,
    fact_key: str,
    fact_type: str,
    source_entity_id: str | None,
    text: str,
    requirements: list[JobRequirementData],
    requirement_keywords: set[str],
    force_selected: bool,
    skill_name: str | None = None,
) -> TailoringPlanFactDraft:
    """Build a single scored tailoring fact entry.

    Args:
        fact_key: Stable fact key.
        fact_type: Fact category.
        source_entity_id: Optional source entity identifier.
        text: Fact text.
        requirements: Job requirement list.
        requirement_keywords: Requirement keyword set.
        force_selected: Marks fact as selected regardless of score.
        skill_name: Optional skill text used for dedicated scoring.

    Returns:
        Scored tailoring fact draft.
    """

    keyword_score = keyword_match_score(text, requirement_keywords)
    skill_score = skill_match_score(skill_name or text, requirement_keywords)
    must_have_hits = count_must_have_hits(text, requirements)
    relevance_score = compute_relevance_score(
        skill_score=skill_score,
        keyword_score=keyword_score,
        must_have_hits=must_have_hits,
    )

    return TailoringPlanFactDraft(
        fact_key=fact_key,
        fact_type=fact_type,
        source_entity_id=source_entity_id,
        text=text,
        relevance_score=relevance_score,
        is_selected=force_selected,
        selection_reason=_build_selection_reason(relevance_score=relevance_score, selected=force_selected),
    )


def _select_fact_keys(
    *,
    facts: list[TailoringPlanFactDraft],
    max_experiences: int,
    max_skills: int,
    max_educations: int,
) -> set[str]:
    """Select fact keys by category and relevance.

    Args:
        facts: Scored fact list.
        max_experiences: Experience selection cap.
        max_skills: Skill selection cap.
        max_educations: Education selection cap.

    Returns:
        Selected fact key set.
    """

    selected: set[str] = set()
    selected.update(_top_keys(facts=facts, fact_type="experience", limit=max_experiences, min_score=1))
    selected.update(_top_keys(facts=facts, fact_type="skill", limit=max_skills, min_score=1))
    selected.update(_top_keys(facts=facts, fact_type="education", limit=max_educations, min_score=1))

    # Keep summary/headline when relevant.
    selected.update(_top_keys(facts=facts, fact_type="summary", limit=1, min_score=5))
    selected.update(_top_keys(facts=facts, fact_type="headline", limit=1, min_score=5))
    return selected


def _top_keys(
    *,
    facts: list[TailoringPlanFactDraft],
    fact_type: str,
    limit: int,
    min_score: int,
) -> set[str]:
    """Return top scoring keys for one fact type.

    Args:
        facts: Scored fact list.
        fact_type: Category to filter.
        limit: Maximum number of items.
        min_score: Minimum score threshold.

    Returns:
        Selected fact key set for the category.
    """

    if limit <= 0:
        return set()

    filtered = [fact for fact in facts if fact.fact_type == fact_type and fact.relevance_score >= min_score]
    ordered = sorted(filtered, key=lambda item: item.relevance_score, reverse=True)
    return {item.fact_key for item in ordered[:limit]}


def _build_selection_reason(*, relevance_score: int, selected: bool) -> str:
    """Build deterministic human-readable selection reason.

    Args:
        relevance_score: Relevance score.
        selected: Selection flag.

    Returns:
        Reason text.
    """

    if selected:
        return f"Selected due to relevance score {relevance_score}."
    return f"Not selected because relevance score {relevance_score} was below category cutoff."


def _resolve_rewritten_text(
    *,
    fact_key: str,
    default_text: str | None,
    selected_facts: dict[str, TailoringPlanFactDraft],
    rewrites: dict[str, str],
) -> str | None:
    """Resolve rewritten text for a selected singleton fact.

    Args:
        fact_key: Fact key to resolve.
        default_text: Source text fallback.
        selected_facts: Selected fact map.
        rewrites: Rewrite map.

    Returns:
        Rewritten text for selected facts, otherwise source text.
    """

    if fact_key not in selected_facts:
        return default_text

    rewritten = rewrites.get(fact_key)
    if rewritten is None:
        return default_text
    return normalize_text(rewritten)
