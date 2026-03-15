"""Deterministic adjudication helpers for LLM-assisted profile import drafts."""

from __future__ import annotations

import re

from app.domain.job_text import normalize_text
from app.domain.profile_import_types import (
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)

_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_EDUCATION_HINT_RE = re.compile(
    r"\b("
    r"bachelor|master|msc|m\.sc|bsc|b\.sc|phd|doctorate|"
    r"university|college|institute|schule|hochschule|diplom|degree"
    r")\b",
    re.IGNORECASE,
)


def adjudicate_profile_import_drafts(
    *,
    llm_draft: ImportedProfileDraft,
    rule_draft: ImportedProfileDraft,
) -> ImportedProfileDraft:
    """Adjudicate LLM proposal with deterministic safeguards.

    The LLM proposal is treated as first-pass placement. Deterministic rules then
    sanitize obvious misplacements and backfill missing values from rule-based
    extraction to improve consistency.

    Args:
        llm_draft: LLM-proposed imported profile draft.
        rule_draft: Rule-based imported profile draft.

    Returns:
        Adjudicated imported profile draft.
    """

    llm_headline = _sanitize_headline(llm_draft.headline)
    rule_headline = _sanitize_headline(rule_draft.headline)
    headline = llm_headline or rule_headline

    llm_location = _sanitize_location(llm_draft.location)
    rule_location = _sanitize_location(rule_draft.location)
    if llm_location and _looks_like_education_fragment(llm_location) and rule_location:
        location = rule_location
    elif llm_location and not _looks_like_education_fragment(llm_location):
        location = llm_location
    else:
        location = rule_location

    summary = _pick_summary(llm_draft.summary, rule_draft.summary)

    experiences = _merge_experiences(llm_draft.experiences, rule_draft.experiences)
    educations = _merge_educations(llm_draft.educations, rule_draft.educations)
    skills = _merge_skills(llm_draft.skills, rule_draft.skills)

    return ImportedProfileDraft(
        full_name=llm_draft.full_name or rule_draft.full_name,
        email=llm_draft.email or rule_draft.email,
        phone=llm_draft.phone or rule_draft.phone,
        location=location,
        headline=headline,
        summary=summary,
        experiences=experiences,
        educations=educations,
        skills=skills,
        unmapped_candidates=[
            *llm_draft.unmapped_candidates,
            *rule_draft.unmapped_candidates,
        ],
    )


def _sanitize_headline(value: str | None) -> str | None:
    """Return headline candidate when it is not a contact bundle."""

    if value is None:
        return None
    cleaned = normalize_text(value)
    if not cleaned:
        return None
    if _is_contact_bundle(cleaned):
        return None
    return cleaned


def _sanitize_location(value: str | None) -> str | None:
    """Return location candidate when normalized and plausible."""

    if value is None:
        return None
    cleaned = normalize_text(value)
    if not cleaned:
        return None
    if "@" in cleaned:
        return None
    if len(cleaned.split()) > 12:
        return None
    return cleaned


def _pick_summary(llm_summary: str | None, rule_summary: str | None) -> str | None:
    """Select summary text while avoiding contact-like content."""

    llm_value = _sanitize_summary(llm_summary)
    rule_value = _sanitize_summary(rule_summary)
    if llm_value and rule_value:
        return llm_value if len(llm_value) >= len(rule_value) else rule_value
    return llm_value or rule_value


def _sanitize_summary(value: str | None) -> str | None:
    """Return summary candidate when not empty and not contact-only."""

    if value is None:
        return None
    cleaned = normalize_text(value)
    if not cleaned:
        return None
    if _is_contact_bundle(cleaned):
        return None
    return cleaned


def _is_contact_bundle(value: str) -> bool:
    """Return whether text is mostly contact/address metadata."""

    lowered = value.lower()
    if _EMAIL_RE.search(lowered):
        return True
    if _PHONE_RE.search(value):
        return True
    separators = lowered.count("|") + lowered.count("·")
    if separators >= 1 and any(token in lowered for token in ("linkedin", "github", "gmail", "outlook")):
        return True
    return False


def _looks_like_education_fragment(value: str) -> bool:
    """Return whether text resembles education content."""

    return _EDUCATION_HINT_RE.search(value) is not None


def _merge_experiences(
    primary: list[ImportedExperienceDraft],
    fallback: list[ImportedExperienceDraft],
) -> list[ImportedExperienceDraft]:
    """Merge experience rows with de-duplication."""

    merged = list(primary)
    keys = {(item.company.strip().lower(), item.title.strip().lower()) for item in merged}
    for item in fallback:
        key = (item.company.strip().lower(), item.title.strip().lower())
        if key in keys:
            continue
        keys.add(key)
        merged.append(item)
    return merged


def _merge_educations(
    primary: list[ImportedEducationDraft],
    fallback: list[ImportedEducationDraft],
) -> list[ImportedEducationDraft]:
    """Merge education rows with de-duplication."""

    merged = list(primary)
    keys = {(item.institution.strip().lower(), item.degree.strip().lower()) for item in merged}
    for item in fallback:
        key = (item.institution.strip().lower(), item.degree.strip().lower())
        if key in keys:
            continue
        keys.add(key)
        merged.append(item)
    return merged


def _merge_skills(
    primary: list[ImportedSkillDraft],
    fallback: list[ImportedSkillDraft],
) -> list[ImportedSkillDraft]:
    """Merge skill rows with case-insensitive de-duplication."""

    merged = list(primary)
    names = {item.skill_name.strip().lower() for item in merged}
    for item in fallback:
        key = item.skill_name.strip().lower()
        if key in names:
            continue
        names.add(key)
        merged.append(item)
    return merged
