"""Pure builders for structured profile import drafts and review fields."""

from __future__ import annotations

import re

from app.domain.job_text import detect_language_fallback, normalize_text
from app.domain.profile_import_types import (
    ImportFieldDraft,
    ImportedEducationDraft,
    ImportedExperienceDraft,
    ImportedProfileDraft,
    ImportedSkillDraft,
)

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_PATTERN = re.compile(r"\+?[0-9][0-9\s().-]{6,}[0-9]")
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z' .-]{2,80}$")
_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
_EXPERIENCE_PATTERN = re.compile(r"^(?P<title>.+?)\s+(?:at|@|bei)\s+(?P<company>.+)$", re.IGNORECASE)
_SKILLS_SPLIT_PATTERN = re.compile(r"[,|/•;]")

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
        "fähigkeiten",
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
}


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

    experiences, educations, skills = _extract_section_entries(lines, source_locator)

    if not skills:
        skills = _extract_inline_skills(lines, source_locator)

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

    for field_path, section_type, value, confidence in (
        ("full_name", "personal", draft.full_name, 80),
        ("email", "personal", draft.email, 95),
        ("phone", "personal", draft.phone, 85),
        ("location", "personal", draft.location, 40),
        ("headline", "summary", draft.headline, 65),
        ("summary", "summary", draft.summary, 55),
    ):
        if not value:
            continue
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
            rows.append(
                ImportFieldDraft(
                    field_path=f"experiences[{index}].{field_name}",
                    section_type="experience",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=70 if field_name in {"company", "title"} else 50,
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
            rows.append(
                ImportFieldDraft(
                    field_path=f"educations[{index}].{field_name}",
                    section_type="education",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=70 if field_name in {"institution", "degree"} else 50,
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
            rows.append(
                ImportFieldDraft(
                    field_path=f"skills[{index}].{field_name}",
                    section_type="skill",
                    extracted_value=value,
                    suggested_value=value,
                    confidence_score=75 if field_name == "skill_name" else 45,
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
    for line in lines[2:20]:
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
        if len(summary_lines) >= 3:
            break

    if summary_lines:
        return " ".join(summary_lines)

    for line in lines[:20]:
        if 40 <= len(line) <= 220:
            return line
    return None


def _extract_section_entries(
    lines: list[str],
    source_locator: str | None,
) -> tuple[list[ImportedExperienceDraft], list[ImportedEducationDraft], list[ImportedSkillDraft]]:
    """Extract section-scoped entries from text lines."""

    experiences: list[ImportedExperienceDraft] = []
    educations: list[ImportedEducationDraft] = []
    skills: list[ImportedSkillDraft] = []

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
        )

    if not experiences:
        experiences = _extract_inline_experiences(lines, source_locator)

    return experiences, educations, _deduplicate_skills(skills)


def _append_section_content(
    *,
    section: str,
    line: str,
    source_locator: str | None,
    experiences: list[ImportedExperienceDraft],
    educations: list[ImportedEducationDraft],
    skills: list[ImportedSkillDraft],
) -> None:
    """Append parsed section content to draft collections."""

    if section == "experience":
        item = _parse_experience_line(line, source_locator)
        if item is not None:
            experiences.append(item)
        return

    if section == "education":
        item = _parse_education_line(line, source_locator)
        if item is not None:
            educations.append(item)
        return

    if section == "skills":
        skills.extend(_parse_skill_line(line, source_locator))


def _extract_inline_skills(lines: list[str], source_locator: str | None) -> list[ImportedSkillDraft]:
    """Extract inline skill keywords when no explicit skills section exists."""

    candidates: list[ImportedSkillDraft] = []
    for line in lines:
        lowered = line.lower()
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
) -> list[ImportedExperienceDraft]:
    """Extract experience-like entries from unsectioned lines."""

    items: list[ImportedExperienceDraft] = []
    seen: set[tuple[str, str]] = set()
    for line in lines:
        item = _parse_experience_line(line, source_locator)
        if item is None:
            continue

        key = (item.title.lower(), item.company.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items


def _parse_experience_line(line: str, source_locator: str | None) -> ImportedExperienceDraft | None:
    """Parse one experience line into structured fields."""

    match = _EXPERIENCE_PATTERN.match(line)
    if match is not None:
        title = normalize_text(match.group("title"))
        company = normalize_text(match.group("company"))
        if title and company:
            return ImportedExperienceDraft(
                company=company,
                title=title,
                description=line,
                source_locator=source_locator,
            )

    lower_line = line.lower()
    for separator in (" at ", " bei ", " @ "):
        if separator not in lower_line:
            continue

        split_pattern = re.compile(re.escape(separator), re.IGNORECASE)
        segments = split_pattern.split(line, maxsplit=1)
        if len(segments) != 2:
            continue

        title = normalize_text(segments[0])
        company = normalize_text(re.split(r"[.,;|]", segments[1], maxsplit=1)[0])
        if not title or not company:
            continue
        if len(title) < 2 or len(company) < 2:
            continue

        return ImportedExperienceDraft(
            company=company,
            title=title,
            description=line,
            source_locator=source_locator,
        )

    return None


def _parse_education_line(line: str, source_locator: str | None) -> ImportedEducationDraft | None:
    """Parse one education line into structured fields."""

    lowered = line.lower()
    if not any(marker in lowered for marker in _DEGREE_MARKERS):
        return None

    segments = [part.strip() for part in re.split(r"\s+-\s+|\s+at\s+|\s+bei\s+", line) if part.strip()]
    if len(segments) < 2:
        return None

    degree = segments[0]
    institution = segments[1]
    year_match = _YEAR_PATTERN.search(line)
    start = year_match.group(0) + "-01-01" if year_match else None

    return ImportedEducationDraft(
        institution=institution,
        degree=degree,
        start_date=start,
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
        cleaned = normalize_text(token)
        if not _is_valid_skill_token(cleaned):
            continue
        skills.append(ImportedSkillDraft(skill_name=cleaned, source_locator=source_locator))
    return skills


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

    if word_count >= 3 and all(word[:1].isupper() for word in token.split() if word):
        return False

    return True


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
