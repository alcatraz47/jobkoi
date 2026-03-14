"""Pure conflict detection helpers for profile imports."""

from __future__ import annotations

from app.domain.profile_import_types import ImportConflictDraft, ImportedProfileDraft


_SCALAR_FIELDS: tuple[str, ...] = (
    "full_name",
    "email",
    "phone",
    "location",
    "headline",
    "summary",
)


def detect_import_conflicts(
    *,
    existing_profile_payload: dict[str, object] | None,
    imported_draft: ImportedProfileDraft,
) -> list[ImportConflictDraft]:
    """Detect conflicts between existing profile data and imported values.

    Args:
        existing_profile_payload: Existing profile response payload or ``None``.
        imported_draft: Imported structured profile draft.

    Returns:
        Detected conflict rows.
    """

    if existing_profile_payload is None:
        return []

    active_version = existing_profile_payload.get("active_version")
    if not isinstance(active_version, dict):
        return []

    conflicts: list[ImportConflictDraft] = []
    conflicts.extend(
        _detect_scalar_conflicts(active_version=active_version, imported_draft=imported_draft)
    )
    conflicts.extend(
        _detect_skill_conflicts(active_version=active_version, imported_draft=imported_draft)
    )
    conflicts.extend(
        _detect_experience_conflicts(active_version=active_version, imported_draft=imported_draft)
    )
    conflicts.extend(
        _detect_education_conflicts(active_version=active_version, imported_draft=imported_draft)
    )
    return conflicts


def _detect_scalar_conflicts(
    *,
    active_version: dict[str, object],
    imported_draft: ImportedProfileDraft,
) -> list[ImportConflictDraft]:
    """Detect scalar-field conflicts."""

    imported_scalar = {
        "full_name": imported_draft.full_name,
        "email": imported_draft.email,
        "phone": imported_draft.phone,
        "location": imported_draft.location,
        "headline": imported_draft.headline,
        "summary": imported_draft.summary,
    }

    conflicts: list[ImportConflictDraft] = []
    for field_name in _SCALAR_FIELDS:
        imported_value = imported_scalar[field_name]
        if not imported_value:
            continue

        existing_value = active_version.get(field_name)
        if not isinstance(existing_value, str) or not existing_value.strip():
            continue

        if existing_value.strip() == imported_value.strip():
            continue

        conflicts.append(
            ImportConflictDraft(
                field_path=field_name,
                conflict_type="value_mismatch",
                existing_value=existing_value,
                imported_value=imported_value,
            )
        )

    return conflicts


def _detect_skill_conflicts(
    *,
    active_version: dict[str, object],
    imported_draft: ImportedProfileDraft,
) -> list[ImportConflictDraft]:
    """Detect duplicate imported skills already present in profile."""

    existing_skills = active_version.get("skills", [])
    if not isinstance(existing_skills, list):
        return []

    existing_names = {
        str(item.get("skill_name", "")).strip().lower()
        for item in existing_skills
        if isinstance(item, dict)
    }

    conflicts: list[ImportConflictDraft] = []
    for index, skill in enumerate(imported_draft.skills):
        if skill.skill_name.lower() not in existing_names:
            continue
        conflicts.append(
            ImportConflictDraft(
                field_path=f"skills[{index}].skill_name",
                conflict_type="duplicate_skill",
                existing_value=skill.skill_name,
                imported_value=skill.skill_name,
            )
        )

    return conflicts


def _detect_experience_conflicts(
    *,
    active_version: dict[str, object],
    imported_draft: ImportedProfileDraft,
) -> list[ImportConflictDraft]:
    """Detect duplicate imported experience entries."""

    existing_experiences = active_version.get("experiences", [])
    if not isinstance(existing_experiences, list):
        return []

    existing_pairs = {
        (
            str(item.get("company", "")).strip().lower(),
            str(item.get("title", "")).strip().lower(),
        )
        for item in existing_experiences
        if isinstance(item, dict)
    }

    conflicts: list[ImportConflictDraft] = []
    for index, item in enumerate(imported_draft.experiences):
        if (item.company.lower(), item.title.lower()) not in existing_pairs:
            continue
        conflicts.append(
            ImportConflictDraft(
                field_path=f"experiences[{index}]",
                conflict_type="duplicate_experience",
                existing_value=f"{item.title} at {item.company}",
                imported_value=f"{item.title} at {item.company}",
            )
        )

    return conflicts


def _detect_education_conflicts(
    *,
    active_version: dict[str, object],
    imported_draft: ImportedProfileDraft,
) -> list[ImportConflictDraft]:
    """Detect duplicate imported education entries."""

    existing_educations = active_version.get("educations", [])
    if not isinstance(existing_educations, list):
        return []

    existing_pairs = {
        (
            str(item.get("institution", "")).strip().lower(),
            str(item.get("degree", "")).strip().lower(),
        )
        for item in existing_educations
        if isinstance(item, dict)
    }

    conflicts: list[ImportConflictDraft] = []
    for index, item in enumerate(imported_draft.educations):
        if (item.institution.lower(), item.degree.lower()) not in existing_pairs:
            continue
        conflicts.append(
            ImportConflictDraft(
                field_path=f"educations[{index}]",
                conflict_type="duplicate_education",
                existing_value=f"{item.degree} at {item.institution}",
                imported_value=f"{item.degree} at {item.institution}",
            )
        )

    return conflicts
