"""Pure builders for structured profile import drafts and review fields."""

from __future__ import annotations

import re

from app.domain.job_text import detect_language_fallback, normalize_text
from app.domain.profile_import_confidence import (
    score_education_field_confidence,
    score_experience_field_confidence,
    score_scalar_field_confidence,
    score_skill_field_confidence,
)
from app.domain.profile_import_types import (
    ImportFieldDraft,
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
    ImportedUnmappedCandidate,
)

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_PATTERN = re.compile(r"\+?[0-9][0-9\s().-]{6,}[0-9]")
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z' .-]{2,80}$")
_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
_SKILLS_SPLIT_PATTERN = re.compile(r"[,|/•;]")

_EXPERIENCE_SEPARATORS = (" at ", " bei ", " @ ")
_COMPANY_CUTOFF_MARKERS = (
    " delivering ",
    " responsible ",
    " with ",
    " where ",
    " using ",
    " focused on ",
)

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience",
        "work experience",
        "employment",
        "berufserfahrung",
        "erfahrung",
    ),
    "education": (
        "education",
        "studies",
        "ausbildung",
        "bildung",
        "academic",
    ),
    "skills": (
        "skills",
        "technologies",
        "tools",
        "faehigkeiten",
        "fahigkeiten",
        "kenntnisse",
    ),
}

_DEGREE_MARKERS = (
    "bachelor",
    "master",
    "phd",
    "msc",
    "bsc",
    "diplom",
    "degree",
    "mba",
)

_SKILL_KEYWORDS: dict[str, str] = {
    "python": "Python",
    "sql": "SQL",
    "fastapi": "FastAPI",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "computer vision": "Computer Vision",
    "opencv": "OpenCV",
    "ocr": "OCR",
    "nlp": "NLP",
    "large language model": "LLM",
    "llm": "LLM",
    "vlm": "VLM",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "Scikit-learn",
    "pandas": "Pandas",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "airflow": "Airflow",
    "dbt": "dbt",
}

_DATE_RANGE_PATTERN = re.compile(
    r"(?P<start>(?:19|20)\d{2})(?:\s*[./-]\s*(?P<start_month>\d{1,2}))?"
    r"\s*(?:-|to|bis|–|—)\s*"
    r"(?P<end>(?:19|20)\d{2}|present|current|heute|now)",
    re.IGNORECASE,
)


def build_imported_profile_from_text(
    *,
    text: str,
    source_locator: str | None,
) -> ImportedProfileDraft:
    """Build structured imported profile data from extracted text.

    Args:
        text: Extracted source text.
        source_locator: Source locator reference.

    Returns:
        Structured imported profile draft.
    """

    lines = _normalized_lines(text)
    email = _extract_email(text)
    phone = _extract_phone(text)
    full_name = _extract_full_name(lines)
    headline = _extract_headline(lines, full_name)
    summary = _extract_summary(lines)

    experiences, educations, skills, unmapped = _extract_section_entries(lines, source_locator)

    if not skills:
        skills = _extract_inline_skills(lines, source_locator)

    if not experiences:
        experiences, inline_unmapped = _extract_inline_experiences(lines, source_locator)
        unmapped.extend(inline_unmapped)

    return ImportedProfileDraft(
        full_name=full_name,
        email=email,
        phone=phone,
        location=None,
        headline=headline,
        summary=summary,
        experiences=experiences,
        educations=educations,
        skills=skills,
        unmapped_candidates=_deduplicate_unmapped(unmapped),
    )


def flatten_imported_profile_to_fields(
    draft: ImportedProfileDraft,
) -> list[ImportFieldDraft]:
    """Flatten imported draft into field-level review rows.

    Args:
        draft: Imported profile draft.

    Returns:
        Ordered field draft rows.
    """

    rows: list[ImportFieldDraft] = []
    order = 0

    for field_path, section_type, value in (
        ("full_name", "personal", draft.full_name),
        ("email", "personal", draft.email),
        ("phone", "personal", draft.phone),
        ("location", "personal", draft.location),
        ("headline", "summary", draft.headline),
        ("summary", "summary", draft.summary),
    ):
        if not value:
            continue
        confidence = score_scalar_field_confidence(field_path=field_path, value=value)
        rows.append(
            ImportFieldDraft(
                field_path=field_path,
                section_type=section_type,
                extracted_value=value,
                suggested_value=value,
                confidence_score=confidence,
                source_locator=None,
                source_excerpt=value,
                sort_order=order,
            )
        )
        order += 1

    for index, item in enumerate(draft.experiences):
        for field_name, value in (
            ("company", item.company),
            ("title", item.title),
            ("start_date", item.start_date),
            ("end_date", item.end_date),
            ("description", item.description),
        ):
            if not value:
                continue
            confidence = score_experience_field_confidence(
                field_name=field_name,
                value=value,
                description=item.description,
            )
            rows.append(
                ImportFieldDraft(
                    field_path=f"experiences[{index}].{field_name}",
                    section_type="experience",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=confidence,
                    source_locator=item.source_locator,
                    source_excerpt=item.description or f"{item.title} at {item.company}",
                    sort_order=order,
                )
            )
            order += 1

    for index, item in enumerate(draft.educations):
        for field_name, value in (
            ("institution", item.institution),
            ("degree", item.degree),
            ("field_of_study", item.field_of_study),
            ("start_date", item.start_date),
            ("end_date", item.end_date),
        ):
            if not value:
                continue
            confidence = score_education_field_confidence(field_name=field_name, value=value)
            rows.append(
                ImportFieldDraft(
                    field_path=f"educations[{index}].{field_name}",
                    section_type="education",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=confidence,
                    source_locator=item.source_locator,
                    source_excerpt=f"{item.degree} at {item.institution}",
                    sort_order=order,
                )
            )
            order += 1

    for index, item in enumerate(draft.skills):
        for field_name, value in (
            ("skill_name", item.skill_name),
            ("level", item.level),
            ("category", item.category),
        ):
            if not value:
                continue
            confidence = score_skill_field_confidence(field_name=field_name, value=value)
            rows.append(
                ImportFieldDraft(
                    field_path=f"skills[{index}].{field_name}",
                    section_type="skill",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=confidence,
                    source_locator=item.source_locator,
                    source_excerpt=item.skill_name,
                    sort_order=order,
                )
            )
            order += 1

    return rows


def detect_import_language(text: str) -> str:
    """Detect source language for imported text.

    Args:
        text: Source text.

    Returns:
        Language code ``en`` or ``de``.
    """

    return detect_language_fallback(text, default_language="en")


def _normalized_lines(text: str) -> list[str]:
    """Return cleaned non-empty lines from source text."""

    normalized = text.replace("\r", "\n")
    lines = [normalize_text(part) for part in normalized.split("\n")]
    return [line for line in lines if line]


def _extract_email(text: str) -> str | None:
    """Extract first email match from text."""

    match = _EMAIL_PATTERN.search(text)
    if match is None:
        return None
    return match.group(0)


def _extract_phone(text: str) -> str | None:
    """Extract first plausible phone number from text."""

    for match in _PHONE_PATTERN.finditer(text):
        candidate = normalize_text(match.group(0))
        digits = re.sub(r"\D", "", candidate)
        if len(digits) < 7 or len(digits) > 15:
            continue
        if len(digits) == 13 and digits.startswith(("978", "979")):
            continue
        return candidate

    return None


def _extract_full_name(lines: list[str]) -> str | None:
    """Extract probable full name from header lines."""

    for line in lines[:8]:
        if "@" in line:
            continue
        if any(char.isdigit() for char in line):
            continue
        if any(symbol in line for symbol in {"{", "}", "http", "©"}):
            continue
        if not _NAME_PATTERN.match(line):
            continue

        words = line.split()
        if 2 <= len(words) <= 5:
            return line
    return None


def _extract_headline(lines: list[str], full_name: str | None) -> str | None:
    """Extract probable professional headline."""

    for line in lines[:14]:
        lowered = line.lower()
        if full_name and line == full_name:
            continue
        if "@" in line or _EMAIL_PATTERN.search(line):
            continue
        if _is_noise_heading_line(lowered):
            continue
        if any(alias in lowered for alias in _SECTION_ALIASES["experience"]):
            continue
        if 6 <= len(line) <= 110:
            return line
    return None


def _extract_summary(lines: list[str]) -> str | None:
    """Extract a compact summary from top lines."""

    summary_lines: list[str] = []
    for line in lines[1:20]:
        lowered = line.lower()
        if _looks_like_section_heading(line):
            break
        if _is_noise_heading_line(lowered):
            continue
        if _EMAIL_PATTERN.search(line) or _PHONE_PATTERN.search(line):
            continue
        if len(line) < 20:
            continue
        summary_lines.append(line)
        if len(summary_lines) >= 2:
            break

    if summary_lines:
        return " ".join(summary_lines)

    for line in lines[:20]:
        if 40 <= len(line) <= 220 and not _is_noise_heading_line(line.lower()):
            return line
    return None


def _extract_section_entries(
    lines: list[str],
    source_locator: str | None,
) -> tuple[
    list[ImportedExperienceDraft],
    list[ImportedEducationDraft],
    list[ImportedSkillDraft],
    list[ImportedUnmappedCandidate],
]:
    """Extract section-scoped entries from text lines."""

    experiences: list[ImportedExperienceDraft] = []
    educations: list[ImportedEducationDraft] = []
    skills: list[ImportedSkillDraft] = []
    unmapped: list[ImportedUnmappedCandidate] = []

    active_section = ""
    for line in lines:
        section, remainder = _detect_section_and_remainder(line)
        if section:
            active_section = section
            if remainder:
                _append_section_content(
                    section=section,
                    line=remainder,
                    source_locator=source_locator,
                    experiences=experiences,
                    educations=educations,
                    skills=skills,
                    unmapped=unmapped,
                )
            continue

        if not active_section:
            continue

        _append_section_content(
            section=active_section,
            line=line,
            source_locator=source_locator,
            experiences=experiences,
            educations=educations,
            skills=skills,
            unmapped=unmapped,
        )

    return experiences, educations, _deduplicate_skills(skills), unmapped


def _append_section_content(
    *,
    section: str,
    line: str,
    source_locator: str | None,
    experiences: list[ImportedExperienceDraft],
    educations: list[ImportedEducationDraft],
    skills: list[ImportedSkillDraft],
    unmapped: list[ImportedUnmappedCandidate],
) -> None:
    """Append parsed section content to draft collections."""

    if section == "experience":
        item = _parse_experience_line(line, source_locator)
        if item is not None:
            experiences.append(item)
            return
        if _should_track_unmapped_line(line):
            unmapped.append(
                ImportedUnmappedCandidate(
                    text=line,
                    section_hint="experience",
                    reason="could_not_parse_experience",
                    source_locator=source_locator,
                )
            )
        return

    if section == "education":
        item = _parse_education_line(line, source_locator)
        if item is not None:
            educations.append(item)
            return
        if _should_track_unmapped_line(line):
            unmapped.append(
                ImportedUnmappedCandidate(
                    text=line,
                    section_hint="education",
                    reason="could_not_parse_education",
                    source_locator=source_locator,
                )
            )
        return

    if section == "skills":
        parsed_skills = _parse_skill_line(line, source_locator)
        if parsed_skills:
            skills.extend(parsed_skills)
            return
        if _should_track_unmapped_line(line):
            unmapped.append(
                ImportedUnmappedCandidate(
                    text=line,
                    section_hint="skills",
                    reason="could_not_parse_skill",
                    source_locator=source_locator,
                )
            )


def _extract_inline_skills(lines: list[str], source_locator: str | None) -> list[ImportedSkillDraft]:
    """Extract inline skill keywords when no explicit skills section exists."""

    candidates: list[ImportedSkillDraft] = []
    for line in lines:
        lowered = line.lower()
        if _is_noise_heading_line(lowered):
            continue
        for keyword, label in _SKILL_KEYWORDS.items():
            if keyword in lowered:
                candidates.append(ImportedSkillDraft(skill_name=label, source_locator=source_locator))

    return _deduplicate_skills(candidates)


def _detect_section_and_remainder(line: str) -> tuple[str, str]:
    """Detect section heading and inline remainder content.

    Args:
        line: Current source line.

    Returns:
        Tuple of section key and heading remainder content.
    """

    normalized = normalize_text(line)
    lowered = normalized.lower()

    for section, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if lowered == alias_lower:
                return section, ""

            for delimiter in (":", "-", "|"):
                prefix = f"{alias_lower}{delimiter}"
                if lowered.startswith(prefix):
                    remainder = normalize_text(normalized[len(alias) + 1 :])
                    return section, remainder

            spaced_prefix = f"{alias_lower} "
            if lowered.startswith(spaced_prefix):
                remainder = normalize_text(normalized[len(alias) :])
                return section, remainder

    return "", ""


def _is_noise_heading_line(lowered_line: str) -> bool:
    """Return whether heading candidate is obvious website navigation noise."""

    return any(
        marker in lowered_line
        for marker in (
            "skip to",
            "toggle menu",
            "primary navigation",
            "footer",
            "powered by",
            "home /",
            "document.documentelement",
        )
    )


def _looks_like_section_heading(line: str) -> bool:
    """Return whether line likely starts a structured section."""

    section, _ = _detect_section_and_remainder(line)
    return bool(section)


def _extract_inline_experiences(
    lines: list[str],
    source_locator: str | None,
) -> tuple[list[ImportedExperienceDraft], list[ImportedUnmappedCandidate]]:
    """Extract experience-like entries from unsectioned lines."""

    items: list[ImportedExperienceDraft] = []
    unmapped: list[ImportedUnmappedCandidate] = []
    seen: set[tuple[str, str]] = set()
    for line in lines:
        if not _looks_like_potential_experience_line(line):
            continue

        item = _parse_experience_line(line, source_locator)
        if item is None:
            if _should_track_unmapped_line(line):
                unmapped.append(
                    ImportedUnmappedCandidate(
                        text=line,
                        section_hint="experience",
                        reason="inline_experience_parse_failed",
                        source_locator=source_locator,
                    )
                )
            continue

        key = (item.title.lower(), item.company.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items, unmapped


def _parse_experience_line(line: str, source_locator: str | None) -> ImportedExperienceDraft | None:
    """Parse one experience line into structured fields."""

    normalized = normalize_text(line)
    if not normalized:
        return None

    lower_line = normalized.lower()
    separator = next((value for value in _EXPERIENCE_SEPARATORS if value in lower_line), None)
    if separator is None:
        return None

    split_pattern = re.compile(re.escape(separator), re.IGNORECASE)
    segments = split_pattern.split(normalized, maxsplit=1)
    if len(segments) != 2:
        return None

    title = normalize_text(segments[0])
    company_raw = normalize_text(segments[1])
    company = _truncate_company_segment(company_raw)

    if not _is_plausible_experience_title(title):
        return None
    if not _is_plausible_company_name(company):
        return None

    start_date, end_date = _extract_date_range(line)

    return ImportedExperienceDraft(
        company=company,
        title=title,
        start_date=start_date,
        end_date=end_date,
        description=normalized,
        source_locator=source_locator,
    )


def _truncate_company_segment(company_raw: str) -> str:
    """Trim company segment by narrative separators."""

    candidate = company_raw
    for marker in _COMPANY_CUTOFF_MARKERS:
        lower_candidate = candidate.lower()
        if marker in lower_candidate:
            candidate = candidate[:lower_candidate.index(marker)]
            break

    candidate = re.split(r"[,;|]", candidate, maxsplit=1)[0]
    return normalize_text(candidate.strip(" .-"))


def _extract_date_range(line: str) -> tuple[str | None, str | None]:
    """Extract a simple year-based date range from one line."""

    match = _DATE_RANGE_PATTERN.search(line)
    if match is None:
        return None, None

    start_year = match.group("start")
    start_month = match.group("start_month")
    start_month_number = _to_month_number(start_month)
    start_date = f"{start_year}-{start_month_number:02d}-01"

    end_raw = match.group("end").lower()
    if end_raw in {"present", "current", "heute", "now"}:
        return start_date, None

    end_year = end_raw
    end_date = f"{end_year}-12-31"
    return start_date, end_date


def _to_month_number(value: str | None) -> int:
    """Return month number from parsed string."""

    if value is None:
        return 1

    try:
        parsed = int(value)
    except ValueError:
        return 1

    if 1 <= parsed <= 12:
        return parsed
    return 1


def _is_plausible_experience_title(value: str) -> bool:
    """Return whether title candidate looks like a role title."""

    lowered = value.lower()
    if len(value) < 2 or len(value) > 80:
        return False
    if len(value.split()) > 8:
        return False
    if _EMAIL_PATTERN.search(value):
        return False
    if "http" in lowered:
        return False
    if any(token in lowered for token in ("currently working", "responsible for", "project was")):
        return False
    return True


def _is_plausible_company_name(value: str) -> bool:
    """Return whether company candidate looks like organization name."""

    lowered = value.lower()
    if len(value) < 2 or len(value) > 80:
        return False
    if len(value.split()) > 7:
        return False
    if "@" in value or "http" in lowered:
        return False
    if any(token in lowered for token in ("delivering", "responsible", "project", "analytics")):
        return False
    return True


def _parse_education_line(line: str, source_locator: str | None) -> ImportedEducationDraft | None:
    """Parse one education line into structured fields."""

    lowered = line.lower()
    if not any(marker in lowered for marker in _DEGREE_MARKERS):
        return None

    segments = [part.strip() for part in re.split(r"\s+-\s+|\s+at\s+|\s+bei\s+", line) if part.strip()]
    if len(segments) < 2:
        return None

    degree = normalize_text(segments[0])
    institution = normalize_text(re.split(r"[,;|]", segments[1], maxsplit=1)[0])

    if len(degree) > 90 or len(institution) > 90:
        return None
    if _looks_like_narrative_line(degree) or _looks_like_narrative_line(institution):
        return None

    start_date, end_date = _extract_date_range(line)
    if start_date is None:
        year_match = _YEAR_PATTERN.search(line)
        start_date = f"{year_match.group(0)}-01-01" if year_match else None

    return ImportedEducationDraft(
        institution=institution,
        degree=degree,
        start_date=start_date,
        end_date=end_date,
        source_locator=source_locator,
    )


def _parse_skill_line(line: str, source_locator: str | None) -> list[ImportedSkillDraft]:
    """Parse one skills-section line into skill rows."""

    cleaned_line = normalize_text(line)
    if not cleaned_line:
        return []

    if _SKILLS_SPLIT_PATTERN.search(cleaned_line) is None:
        return []

    skills: list[ImportedSkillDraft] = []
    for token in _SKILLS_SPLIT_PATTERN.split(cleaned_line):
        cleaned = _normalize_skill_token(normalize_text(token))
        if not _is_valid_skill_token(cleaned):
            continue
        skills.append(ImportedSkillDraft(skill_name=cleaned, source_locator=source_locator))
    return skills


def _normalize_skill_token(token: str) -> str:
    """Normalize extracted skill token into canonical value."""

    lowered = token.lower()
    if lowered in {"llms", "large language models"}:
        return "LLM"
    if lowered in {"vlms", "vision language models"}:
        return "VLM"
    if lowered == "mlops":
        return "MLOps"
    return token


def _is_valid_skill_token(token: str) -> bool:
    """Return whether parsed token is valid as skill value."""

    if len(token) < 2 or len(token) > 64:
        return False

    lowered = token.lower()
    if lowered in {
        "home",
        "projects",
        "experience",
        "skills",
        "publications",
        "blog",
        "cv",
        "linkedin",
        "toggle menu",
    }:
        return False

    if lowered.startswith("view "):
        return False

    if any(part in lowered for part in ("currently", "working", "selected", "follow", "portfolio")):
        return False

    if "." in token:
        return False

    word_count = len(token.split())
    if word_count > 4:
        return False

    if _looks_like_narrative_line(token):
        return False

    return True


def _looks_like_potential_experience_line(line: str) -> bool:
    """Return whether line can plausibly encode experience tuple."""

    lowered = line.lower()
    return any(separator.strip() in lowered for separator in _EXPERIENCE_SEPARATORS)


def _should_track_unmapped_line(line: str) -> bool:
    """Return whether line should be retained as unmapped evidence."""

    cleaned = normalize_text(line)
    if len(cleaned) < 20:
        return False
    if _is_noise_heading_line(cleaned.lower()):
        return False
    return True


def _looks_like_narrative_line(value: str) -> bool:
    """Return whether value appears to be long narrative sentence."""

    lowered = value.lower()
    if len(value.split()) > 9:
        return True
    return any(token in lowered for token in (" delivering ", " responsible ", " project "))


def _deduplicate_skills(skills: list[ImportedSkillDraft]) -> list[ImportedSkillDraft]:
    """Return skills deduplicated by lower-case skill name."""

    seen: set[str] = set()
    deduplicated: list[ImportedSkillDraft] = []
    for item in skills:
        key = item.skill_name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


def _deduplicate_unmapped(
    candidates: list[ImportedUnmappedCandidate],
) -> list[ImportedUnmappedCandidate]:
    """Return unmapped candidate rows deduplicated by normalized text."""

    deduplicated: list[ImportedUnmappedCandidate] = []
    seen: set[str] = set()
    for item in candidates:
        key = normalize_text(item.text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated
