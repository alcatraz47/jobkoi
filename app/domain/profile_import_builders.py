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
_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' .-]{2,80}$")
_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
_SKILLS_SPLIT_PATTERN = re.compile(r"[,|•;]|\s+/\s+")

_EXPERIENCE_SEPARATORS = (" at ", " bei ", " @ ")
_EXPERIENCE_DASH_SEPARATORS = (" - ", " – ", " — ", " | ")
_COMPANY_CUTOFF_MARKERS = (
    " delivering ",
    " responsible ",
    " with ",
    " where ",
    " using ",
    " focused on ",
    " integrating ",
    " building ",
    " led ",
    " leading ",
    " currently ",
)
_ADDRESS_TOKENS = (
    "str.",
    "straße",
    "street",
    "st.",
    "road",
    "rd.",
    "avenue",
    "ave",
    "platz",
    "allee",
    "weg",
)

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "career history",
        "work history",
        "employment",
        "berufserfahrung",
        "erfahrung",
    ),
    "education": (
        "education",
        "education & training",
        "studies",
        "ausbildung",
        "bildung",
        "bildungsgang",
        "academic",
    ),
    "skills": (
        "skills",
        "core skills",
        "technical skills",
        "skills & tools",
        "technologies",
        "tools",
        "tech stack",
        "faehigkeiten",
        "fahigkeiten",
        "kenntnisse",
        "kompetenzen",
    ),
}

_DEGREE_MARKERS = (
    "bachelor",
    "master",
    "phd",
    "msc",
    "bsc",
    "bs",
    "ba",
    "ma",
    "mtech",
    "btech",
    "b.eng",
    "m.eng",
    "diplom",
    "degree",
    "mba",
)

_EDUCATION_MARKERS = (
    "university",
    "college",
    "institute",
    "school",
    "faculty",
    "expected",
    "graduation",
    "semester",
    "thesis",
    "dissertation",
    "bachelor",
    "master",
    "phd",
    "msc",
    "bsc",
    "mba",
    "diplom",
)

_COMPANY_HINTS = (
    "gmbh",
    "ag",
    "inc",
    "llc",
    "ltd",
    "corp",
    "corporation",
    "company",
    "technologies",
    "systems",
    "labs",
    "lab",
    "institute",
    "university",
    "college",
    "group",
)

_ROLE_HINTS = (
    "engineer",
    "developer",
    "scientist",
    "analyst",
    "manager",
    "architect",
    "consultant",
    "specialist",
    "researcher",
    "intern",
    "student",
    "working student",
    "lead",
    "head",
    "director",
    "ingenieur",
    "ingenieurin",
    "entwickler",
    "entwicklerin",
    "berater",
    "beraterin",
    "forscher",
    "forscherin",
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

_PRESENT_STATUS_TOKENS = {"present", "current", "now", "heute"}
_TRAILING_YEAR_IN_TITLE_PATTERN = re.compile(
    r"(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+)?"
    r"(?:19|20)\d{2}$",
    re.IGNORECASE,
)
_TRAILING_EXPERIENCE_DATE_RANGE_PATTERN = re.compile(
    r"(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+)?"
    r"(?:19|20)\d{2}\s*(?:-|to|bis|–|—)\s*"
    r"(?:(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+)?(?:19|20)\d{2}|present|current|heute|now)$",
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
    lines_with_breaks = _normalized_lines_with_breaks(text)

    email = _extract_email(text)
    phone = _extract_phone(text)
    full_name = _extract_full_name(lines)
    headline = _extract_headline(lines, full_name)
    location = _extract_location(lines, full_name=full_name, headline=headline)
    summary = _extract_summary(lines)

    experiences, educations, skills, unmapped = _extract_section_entries(lines_with_breaks, source_locator)

    if not skills:
        skills = _extract_inline_skills(lines, source_locator)

    if not experiences:
        experiences, inline_unmapped = _extract_inline_experiences(lines, source_locator)
        unmapped.extend(inline_unmapped)

    if not educations:
        educations, inline_unmapped = _extract_inline_educations(lines, source_locator)
        unmapped.extend(inline_unmapped)

    return ImportedProfileDraft(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        headline=headline,
        summary=summary,
        experiences=experiences,
        educations=educations,
        skills=_deduplicate_skills(skills),
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
            include_blank_title = field_name == "title" and not value and bool(item.company or item.description)
            if not value and not include_blank_title:
                continue
            field_value = value or ""
            confidence = score_experience_field_confidence(
                field_name=field_name,
                value=field_value,
                description=item.description,
            )
            rows.append(
                ImportFieldDraft(
                    field_path=f"experiences[{index}].{field_name}",
                    section_type="experience",
                    extracted_value=field_value,
                    suggested_value=field_value,
                    confidence_score=confidence,
                    source_locator=item.source_locator,
                    source_excerpt=item.source_excerpt or item.description or f"{item.title} at {item.company}",
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
                    source_excerpt=item.source_excerpt or f"{item.degree} at {item.institution}",
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
                    source_excerpt=item.source_excerpt or item.skill_name,
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


def _normalized_lines_with_breaks(text: str) -> list[str]:
    """Return normalized lines preserving section breaks as empty strings."""

    normalized = text.replace("\r", "\n")
    rows: list[str] = []
    for raw in normalized.split("\n"):
        cleaned = normalize_text(raw)
        if cleaned:
            rows.append(cleaned)
            continue

        if rows and rows[-1] != "":
            rows.append("")

    while rows and rows[0] == "":
        rows.pop(0)
    while rows and rows[-1] == "":
        rows.pop()

    return rows


def _extract_location(
    lines: list[str],
    *,
    full_name: str | None,
    headline: str | None,
) -> str | None:
    """Extract probable location from header-like lines."""

    for line in lines[:14]:
        lowered = line.lower()
        if not line or line == full_name or line == headline:
            continue
        if _looks_like_section_heading(line) or _is_noise_heading_line(lowered):
            continue
        if len(line) > 90:
            continue
        if "http" in lowered or "linkedin" in lowered or "github" in lowered:
            continue
        if _looks_like_education_line(line):
            continue

        if _PHONE_PATTERN.search(line):
            contact_location = _extract_location_from_contact_line(line)
            if contact_location:
                return contact_location
            continue

        if _EMAIL_PATTERN.search(line):
            continue

        if _is_location_candidate(line):
            return line

    return None


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

        context_start = max(0, match.start() - 32)
        context_end = min(len(text), match.end() + 16)
        context = text[context_start:context_end].lower()
        previous_char = text[match.start() - 1] if match.start() > 0 else ""
        next_char = text[match.end()] if match.end() < len(text) else ""
        if "http" in context or "www." in context:
            continue
        if previous_char == "/" or (previous_char in {"/", "_", "-"} and next_char.isalpha()):
            continue

        return candidate

    return None


def _extract_full_name(lines: list[str]) -> str | None:
    """Extract probable full name from header lines."""

    best_candidate: str | None = None
    best_score = -1

    for line in lines[:120]:
        lowered = line.lower()
        if "@" in line:
            continue
        if any(char.isdigit() for char in line):
            continue
        if any(symbol in line for symbol in {"{", "}", "http", "©"}):
            continue
        if _is_profile_label_line(line):
            continue
        if _contains_role_keyword(line):
            continue
        if any(token in lowered for token in ("engineering", "computer", "vision", "nlp", "llm", "vlm", "skill")):
            continue
        if not _NAME_PATTERN.match(line):
            continue

        words = line.split()
        if not 2 <= len(words) <= 5:
            continue

        score = 0
        if 2 <= len(words) <= 4:
            score += 2
        if len(line) <= 30:
            score += 1
        if all(word[:1].isupper() for word in words if word.lower() not in {"von", "de", "da", "bin", "al", "el"}):
            score += 1
        if score > best_score:
            best_candidate = line
            best_score = score

    return best_candidate


def _extract_headline(lines: list[str], full_name: str | None) -> str | None:
    """Extract probable professional headline."""

    candidate_lines: list[str] = []
    if full_name is not None:
        for index, line in enumerate(lines):
            if line != full_name:
                continue
            candidate_lines.extend(lines[index + 1 : index + 8])
            break

    if not candidate_lines:
        for line in lines[:24]:
            if _looks_like_section_heading(line):
                break
            candidate_lines.append(line)

    fallback: str | None = None
    seen: set[str] = set()
    for line in candidate_lines:
        if line in seen:
            continue
        seen.add(line)
        lowered = line.lower()
        if full_name and line == full_name:
            continue
        if "@" in line or _EMAIL_PATTERN.search(line):
            continue
        if _PHONE_PATTERN.search(line):
            continue
        if _is_noise_heading_line(lowered) or _is_profile_label_line(line):
            continue
        if any(alias in lowered for alias in _SECTION_ALIASES["experience"]):
            continue
        if _is_location_candidate(line):
            continue
        if _looks_like_education_line(line):
            continue
        if line.endswith((".", "!", "?")):
            continue
        if _looks_like_narrative_line(line):
            continue

        word_count = len(line.split())
        if not (2 <= word_count <= 12 and 6 <= len(line) <= 110):
            continue
        if _contains_role_keyword(line):
            return line
        if fallback is None:
            fallback = line

    return fallback


def _is_location_candidate(value: str) -> bool:
    """Return whether one line likely encodes location information."""

    lowered = value.lower()
    if "@" in value or "http" in lowered:
        return False
    if _looks_like_education_line(value):
        return False

    digits = sum(1 for char in value if char.isdigit())
    if digits > 5:
        return False

    if "," not in value:
        return False

    if len(value.split()) > 8:
        return False

    return True


def _extract_location_from_contact_line(line: str) -> str | None:
    """Extract location segment from contact bundle line when present."""

    segments = [normalize_text(part) for part in re.split(r"[|•]", line)]
    for segment in segments:
        if not segment:
            continue
        if _PHONE_PATTERN.search(segment) or _EMAIL_PATTERN.search(segment):
            continue
        if _is_location_candidate(segment):
            return segment

    return None


def _looks_like_education_line(value: str) -> bool:
    """Return whether one line likely belongs to education data."""

    collapsed = value.lower().replace(".", "")
    markers = tuple(marker.replace(".", "") for marker in _EDUCATION_MARKERS)
    return any(re.search(rf"\b{re.escape(marker)}\b", collapsed) for marker in markers)


def _extract_summary(lines: list[str]) -> str | None:
    """Extract a compact summary from top lines."""

    summary_lines: list[str] = []
    for line in lines[1:24]:
        lowered = line.lower()
        if _looks_like_section_heading(line):
            break
        if _is_noise_heading_line(lowered) or _is_profile_label_line(line):
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

    for line in lines[:24]:
        if 40 <= len(line) <= 220 and not _is_noise_heading_line(line.lower()) and not _is_profile_label_line(line):
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
    section_buffer: list[str] = []

    for line in lines:
        if line == "":
            _append_section_buffer(
                section=active_section,
                lines=section_buffer,
                source_locator=source_locator,
                experiences=experiences,
                educations=educations,
                skills=skills,
                unmapped=unmapped,
            )
            section_buffer = []
            continue

        section, remainder = _detect_section_and_remainder(line)
        if section:
            _append_section_buffer(
                section=active_section,
                lines=section_buffer,
                source_locator=source_locator,
                experiences=experiences,
                educations=educations,
                skills=skills,
                unmapped=unmapped,
            )
            section_buffer = []
            active_section = section
            if remainder:
                section_buffer.append(remainder)
            continue

        if active_section:
            section_buffer.append(line)

    _append_section_buffer(
        section=active_section,
        lines=section_buffer,
        source_locator=source_locator,
        experiences=experiences,
        educations=educations,
        skills=skills,
        unmapped=unmapped,
    )

    return experiences, educations, _deduplicate_skills(skills), unmapped


def _append_section_buffer(
    *,
    section: str,
    lines: list[str],
    source_locator: str | None,
    experiences: list[ImportedExperienceDraft],
    educations: list[ImportedEducationDraft],
    skills: list[ImportedSkillDraft],
    unmapped: list[ImportedUnmappedCandidate],
) -> None:
    """Parse one buffered section chunk and append parsed content."""

    if not section or not lines:
        return

    if section == "skills":
        for line in lines:
            parsed_skills = _parse_skill_line(line, source_locator)
            if parsed_skills:
                skills.extend(parsed_skills)
                continue

            if _should_track_unmapped_line(line):
                unmapped.append(
                    ImportedUnmappedCandidate(
                        text=line,
                        section_hint="skills",
                        reason="could_not_parse_skill",
                        source_locator=source_locator,
                    )
                )
        return

    if section == "experience":
        parsed_any = False
        for block in _split_experience_section_blocks(lines):
            block_item = _parse_experience_block(block, source_locator)
            if block_item is not None:
                parsed_any = True
                experiences.append(block_item)
                continue

            for line in block:
                item = _parse_experience_line(line, source_locator)
                if item is not None:
                    parsed_any = True
                    experiences.append(item)

        if not parsed_any:
            for line in lines:
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
        block_item = _parse_education_block(lines, source_locator)
        if block_item is not None:
            educations.append(block_item)
            return

        parsed_any = False
        for line in lines:
            item = _parse_education_line(line, source_locator)
            if item is not None:
                parsed_any = True
                educations.append(item)

        if not parsed_any:
            for line in lines:
                if _should_track_unmapped_line(line):
                    unmapped.append(
                        ImportedUnmappedCandidate(
                            text=line,
                            section_hint="education",
                            reason="could_not_parse_education",
                            source_locator=source_locator,
                        )
                    )


def _split_experience_section_blocks(lines: list[str]) -> list[list[str]]:
    """Split one experience section into probable per-role blocks."""

    blocks: list[list[str]] = []
    current: list[str] = []

    for raw_line in lines:
        line = normalize_text(raw_line)
        if not line:
            continue

        if not current:
            current = [line]
            continue

        if _looks_like_experience_block_start(line):
            blocks.append(current)
            current = [line]
            continue

        current.append(line)

    if current:
        blocks.append(current)

    return blocks or ([lines] if lines else [])


def _looks_like_experience_block_start(line: str) -> bool:
    """Return whether one line likely starts a new experience entry."""

    lowered = line.lower()
    if lowered.startswith(("location:", "standort:", "tools/stack:", "stack:", "tech:", "technologies:")):
        return False
    if line.startswith(("-", "•", "*")):
        return False
    if len(line) > 140:
        return False

    has_year = _YEAR_PATTERN.search(line) is not None
    has_end_marker = any(token in lowered for token in ("present", "current", "heute", "now"))
    has_second_year = len(_YEAR_PATTERN.findall(line)) >= 2
    return has_year and (has_end_marker or has_second_year)


def _parse_experience_block(lines: list[str], source_locator: str | None) -> ImportedExperienceDraft | None:
    """Parse one multi-line experience block into one structured entry."""

    cleaned_lines = [normalize_text(line) for line in lines if normalize_text(line)]
    if not cleaned_lines:
        return None

    joined = normalize_text(" ".join(cleaned_lines))
    description = joined[:1200] if joined else None
    start_date, end_date = _extract_date_range(joined)

    if len(cleaned_lines) >= 2:
        first = cleaned_lines[0]
        second = cleaned_lines[1]

        header_company = _extract_company_from_date_header(first)
        role_title = _extract_role_only_title(second)
        if header_company and role_title:
            return ImportedExperienceDraft(
                company=header_company,
                title=role_title,
                start_date=start_date,
                end_date=end_date,
                description=description,
                source_locator=source_locator,
                source_excerpt=description,
            )

        if header_company and second.startswith(("-", "•", "*")):
            return ImportedExperienceDraft(
                company=header_company,
                title="",
                start_date=start_date,
                end_date=end_date,
                description=description,
                source_locator=source_locator,
                source_excerpt=description,
            )

        if header_company and not second.startswith(("-", "•", "*")):
            second_title = _clean_experience_title(
                re.split(r"\b(?:location|standort)\b", second, maxsplit=1, flags=re.IGNORECASE)[0]
            )
            if second_title and _is_plausible_experience_title(second_title) and not _looks_like_narrative_line(second_title):
                return ImportedExperienceDraft(
                    company=header_company,
                    title=second_title,
                    start_date=start_date,
                    end_date=end_date,
                    description=description,
                    source_locator=source_locator,
                    source_excerpt=description,
                )

        first_title = _clean_experience_title(first)
        second_company = _truncate_company_segment(second)
        if start_date is not None and _is_plausible_experience_title(first_title) and _is_plausible_company_name(second_company):
            return ImportedExperienceDraft(
                company=second_company,
                title=first_title,
                start_date=start_date,
                end_date=end_date,
                description=description,
                source_locator=source_locator,
                source_excerpt=description,
            )

    for line in cleaned_lines:
        parsed = _parse_experience_line(line, source_locator)
        if parsed is not None:
            return ImportedExperienceDraft(
                company=parsed.company,
                title=parsed.title,
                start_date=parsed.start_date,
                end_date=parsed.end_date,
                description=description or parsed.description,
                source_locator=source_locator,
                source_excerpt=description or parsed.source_excerpt or parsed.description,
            )

    header_company = _extract_company_from_date_header(cleaned_lines[0])
    if header_company is not None:
        return ImportedExperienceDraft(
            company=header_company,
            title="",
            start_date=start_date,
            end_date=end_date,
            description=description,
            source_locator=source_locator,
            source_excerpt=description,
        )

    if len(cleaned_lines) < 2:
        return None

    first = _clean_experience_title(cleaned_lines[0])
    second_raw = cleaned_lines[1]
    second = _truncate_company_segment(second_raw)
    if second_raw.startswith(("-", "•", "*")) or _looks_like_narrative_line(second):
        return None
    if _is_plausible_experience_title(first) and _is_plausible_company_name(second):
        return ImportedExperienceDraft(
            company=second,
            title=first,
            start_date=start_date,
            end_date=end_date,
            description=description,
            source_locator=source_locator,
            source_excerpt=description,
        )

    if (
        _is_plausible_company_name(first)
        and _is_plausible_experience_title(second)
        and _contains_role_keyword(second)
        and not _contains_role_keyword(first)
    ):
        return ImportedExperienceDraft(
            company=first,
            title=second,
            start_date=start_date,
            end_date=end_date,
            description=description,
            source_locator=source_locator,
            source_excerpt=description,
        )

    return None


def _extract_company_from_date_header(line: str) -> str | None:
    """Extract company name from a header line containing a date range."""

    candidate = re.sub(r"\([^)]*(?:19|20)\d{2}[^)]*\)", "", line).strip(" -|,;()")
    if candidate == line:
        match = _DATE_RANGE_PATTERN.search(line)
        if match is None:
            return None
        candidate = line[: match.start()].strip(" -|,;()")

    candidate = _truncate_company_segment(normalize_text(candidate))
    if not candidate or not _is_plausible_company_name(candidate):
        return None
    if _contains_role_keyword(candidate) and _company_hint_score(candidate) == 0:
        return None
    return candidate


def _extract_role_only_title(line: str) -> str | None:
    """Extract title from a line that starts with a role marker."""

    match = re.search(r"\brole\s*[:\-]\s*(?P<title>.+)$", line, flags=re.IGNORECASE)
    if match is None:
        return None

    title = normalize_text(match.group("title"))
    title = re.split(r"\b(?:location|standort)\b", title, maxsplit=1, flags=re.IGNORECASE)[0]
    title = re.split(r"\s+[-|]\s+", title, maxsplit=1)[0]
    title = _clean_experience_title(title)
    if not title or not _is_plausible_experience_title(title):
        return None
    return title


def _parse_education_block(lines: list[str], source_locator: str | None) -> ImportedEducationDraft | None:
    """Parse one multi-line education block into one structured entry."""

    for line in lines:
        parsed = _parse_education_line(line, source_locator)
        if parsed is not None:
            return parsed

    if len(lines) < 2:
        return None

    first = normalize_text(lines[0])
    second = normalize_text(lines[1])
    if not _looks_like_degree_text(first):
        return None

    institution = normalize_text(re.split(r"[,;|]", second, maxsplit=1)[0])
    if not _is_plausible_company_name(institution):
        return None

    joined = normalize_text(" ".join(lines))
    start_date, end_date = _extract_date_range(joined)
    if start_date is None:
        year_match = _YEAR_PATTERN.search(joined)
        start_date = f"{year_match.group(0)}-01-01" if year_match else None

    return ImportedEducationDraft(
        institution=institution,
        degree=first,
        start_date=start_date,
        end_date=end_date,
        source_locator=source_locator,
        source_excerpt=joined[:1200],
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
                candidates.append(ImportedSkillDraft(skill_name=label, source_locator=source_locator, source_excerpt=line))

    return _deduplicate_skills(candidates)


def _detect_section_and_remainder(line: str) -> tuple[str, str]:
    """Detect section heading and inline remainder content.

    Args:
        line: Current source line.

    Returns:
        Tuple of section key and heading remainder content.
    """

    normalized = normalize_text(line)
    normalized = normalized.strip("•*- ")
    lowered = normalized.lower()

    for section, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if lowered == alias_lower or lowered == f"{alias_lower}:":
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


def _is_profile_label_line(line: str) -> bool:
    """Return whether one line is likely navigation, UI, or section label noise."""

    lowered = normalize_text(line).lower()
    if not lowered:
        return False
    if lowered in {
        "/",
        "home",
        "projects",
        "experience",
        "skills",
        "publications",
        "publication",
        "blog",
        "cv",
        "follow",
        "github",
        "linkedin",
        "email",
        "overview",
        "impact",
        "tech",
        "tooling",
        "capstone",
        "objective",
        "profile",
        "summary",
        "about",
        "contact",
    }:
        return True
    if lowered.startswith((
        "linkedin",
        "github",
        "follow",
        "download cv",
        "skills at a glance",
        "technical skills",
        "soft skills",
        "language skills",
        "what i did",
        "role:",
        "location:",
        "tools/stack:",
        "stack:",
        "tech:",
    )):
        return True
    return False


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


def _extract_inline_educations(
    lines: list[str],
    source_locator: str | None,
) -> tuple[list[ImportedEducationDraft], list[ImportedUnmappedCandidate]]:
    """Extract education-like entries from unsectioned lines."""

    items: list[ImportedEducationDraft] = []
    unmapped: list[ImportedUnmappedCandidate] = []
    seen: set[tuple[str, str]] = set()

    for line in lines:
        if _looks_like_section_heading(line):
            continue
        if _is_noise_heading_line(line.lower()):
            continue
        if not _looks_like_education_line(line):
            continue

        item = _parse_education_line(line, source_locator)
        if item is None:
            if _should_track_unmapped_line(line):
                unmapped.append(
                    ImportedUnmappedCandidate(
                        text=line,
                        section_hint="education",
                        reason="inline_education_parse_failed",
                        source_locator=source_locator,
                    )
                )
            continue

        key = (item.institution.lower(), item.degree.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items, unmapped


def _parse_experience_line(line: str, source_locator: str | None) -> ImportedExperienceDraft | None:
    """Parse one experience line into structured fields."""

    normalized = normalize_text(line)
    if not normalized or len(normalized) > 400:
        return None
    if normalized.startswith(("-", "•", "*")):
        return None

    title = ""
    company = ""

    parsed_role = _parse_experience_role_pattern_line(normalized)
    if parsed_role is not None:
        title, company = parsed_role

    lower_line = normalized.lower()
    separator = next((value for value in _EXPERIENCE_SEPARATORS if value in lower_line), None)
    if separator is not None and (not title or not company):
        split_pattern = re.compile(re.escape(separator), re.IGNORECASE)
        segments = split_pattern.split(normalized, maxsplit=1)
        if len(segments) == 2:
            title = normalize_text(segments[0])
            company = _truncate_company_segment(normalize_text(segments[1]))

    if not title or not company:
        parsed_dash = _parse_experience_dash_or_pipe_line(normalized)
        if parsed_dash is not None:
            title, company = parsed_dash

    title = _clean_experience_title(title)
    company = _strip_leading_present_status(company)
    if _is_present_status(company):
        company = _extract_company_after_present(normalized) or company

    title, company = _rebalance_experience_fields(title=title, company=company)

    if not title or not company:
        return None

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
        source_excerpt=normalized,
    )


def _parse_experience_role_pattern_line(line: str) -> tuple[str, str] | None:
    """Parse lines with explicit ``Role:`` patterns into title/company tuple."""

    pattern = re.compile(
        r"^(?P<company>.+?)\s*(?:\([^)]*\))?\s+role\s*[:\-]\s*(?P<title>.+)$",
        flags=re.IGNORECASE,
    )
    match = pattern.search(line)
    if match is None:
        return None

    company = _truncate_company_segment(normalize_text(match.group("company")))
    title = normalize_text(match.group("title"))
    title = re.split(r"\b(?:location|standort)\b", title, maxsplit=1, flags=re.IGNORECASE)[0]
    title = re.split(r"\s+[-|]\s+", title, maxsplit=1)[0]
    title = normalize_text(title)

    if not title or not company:
        return None

    return title, company


def _clean_experience_title(value: str) -> str:
    """Remove trailing year/date fragments from experience title candidates."""

    cleaned = normalize_text(value)
    cleaned = _TRAILING_EXPERIENCE_DATE_RANGE_PATTERN.sub("", cleaned).strip(" -|,;")
    cleaned = _TRAILING_YEAR_IN_TITLE_PATTERN.sub("", cleaned).strip(" -|,;")
    return normalize_text(cleaned)


def _is_present_status(value: str) -> bool:
    """Return whether one value is only a present/current status token."""

    lowered = normalize_text(value).lower()
    return lowered in _PRESENT_STATUS_TOKENS


def _strip_leading_present_status(value: str) -> str:
    """Remove leading temporal status tokens from company candidates."""

    cleaned = normalize_text(value)
    cleaned = re.sub(r"^(?:present|current|heute|now)\b[:,-]?\s*", "", cleaned, flags=re.IGNORECASE)
    return normalize_text(cleaned)


def _extract_company_after_present(line: str) -> str | None:
    """Extract probable company text that follows present/current status."""

    match = re.search(r"\b(?:present|current|heute|now)\b\s+(?P<company>.+)$", line, flags=re.IGNORECASE)
    if match is None:
        return None

    candidate = _truncate_company_segment(normalize_text(match.group("company")))
    candidate = _strip_leading_present_status(candidate)
    if not candidate:
        return None
    if _is_present_status(candidate):
        return None
    return candidate


def _parse_experience_dash_or_pipe_line(line: str) -> tuple[str, str] | None:
    """Parse dash/pipe separated line into title/company tuple."""

    for separator in _EXPERIENCE_DASH_SEPARATORS:
        if separator not in line:
            continue

        left_raw, right_raw = line.split(separator, maxsplit=1)
        left = normalize_text(left_raw).strip(" .-")
        right = normalize_text(right_raw).strip(" .-")
        if not left or not right:
            continue

        left_hint = _company_hint_score(left)
        right_hint = _company_hint_score(right)

        if left_hint > right_hint:
            title = right
            company = left
        elif right_hint > left_hint:
            title = left
            company = right
        else:
            title = left
            company = right

        if _is_plausible_experience_title(title) and _is_plausible_company_name(company):
            return title, company

        if _is_plausible_experience_title(company) and _is_plausible_company_name(title):
            return company, title

    return None


def _rebalance_experience_fields(*, title: str, company: str) -> tuple[str, str]:
    """Swap title/company when heuristic evidence indicates inversion."""

    clean_title = _clean_experience_title(title)
    clean_company = _truncate_company_segment(_strip_leading_present_status(company))

    title_company_hint = _company_hint_score(clean_title)
    company_company_hint = _company_hint_score(clean_company)
    title_role_hint = 1 if _contains_role_keyword(clean_title) else 0
    company_role_hint = 1 if _contains_role_keyword(clean_company) else 0

    should_swap = (
        title_company_hint > company_company_hint
        and company_role_hint > title_role_hint
        and not _looks_like_degree_text(clean_company)
    )
    if should_swap:
        clean_title, clean_company = clean_company, clean_title

    return clean_title, clean_company


def _contains_role_keyword(value: str) -> bool:
    """Return whether title text contains common role keywords."""

    lowered = value.lower()
    return any(token in lowered for token in _ROLE_HINTS)


def _company_hint_score(value: str) -> int:
    """Return organization-hint score for one candidate text."""

    lowered = value.lower()
    return sum(1 for token in _COMPANY_HINTS if token in lowered)


def _truncate_company_segment(company_raw: str) -> str:
    """Trim company segment by narrative separators."""

    candidate = company_raw
    for marker in _COMPANY_CUTOFF_MARKERS:
        lower_candidate = candidate.lower()
        if marker in lower_candidate:
            candidate = candidate[:lower_candidate.index(marker)]
            break

    candidate = re.split(r"[,;|]", candidate, maxsplit=1)[0]
    candidate = _strip_company_address_tail(candidate)
    return normalize_text(candidate.strip(" .-"))


def _strip_company_address_tail(value: str) -> str:
    """Remove address-like suffix tokens from company candidate."""

    tokens = value.split()
    if not tokens:
        return value

    for index, token in enumerate(tokens):
        lowered = token.lower().strip(".,;")
        if index < 2:
            continue
        if _is_address_like_token(lowered):
            return " ".join(tokens[:index]).strip()
        if re.search(r"\d", lowered):
            return " ".join(tokens[:index]).strip()

    return value


def _is_address_like_token(value: str) -> bool:
    """Return whether one token likely belongs to an address suffix."""

    if any(marker in value for marker in _ADDRESS_TOKENS):
        return True
    return bool(re.search(r"(?:^|[-_])(str|strasse|straße)(?:\.|$)", value))


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
    if len(value) < 2 or len(value) > 120:
        return False
    if len(value.split()) > 14:
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
    if len(value) < 2 or len(value) > 120:
        return False
    if len(value.split()) > 14:
        return False
    if "@" in value or "http" in lowered:
        return False
    if _is_present_status(value):
        return False
    if _TRAILING_YEAR_IN_TITLE_PATTERN.search(value):
        return False
    if any(token in lowered for token in ("delivering", "responsible", "project objective")):
        return False
    return True


def _parse_education_line(line: str, source_locator: str | None) -> ImportedEducationDraft | None:
    """Parse one education line into structured fields."""

    normalized = normalize_text(line)
    if not normalized:
        return None

    if not _looks_like_degree_text(normalized):
        return None

    segments = [
        part.strip()
        for part in re.split(r"\s+-\s+|\s+at\s+|\s+bei\s+|\s+\|\s+", normalized)
        if part.strip()
    ]

    if len(segments) >= 2:
        left = normalize_text(segments[0])
        right = normalize_text(re.split(r"[,;|]", segments[1], maxsplit=1)[0])
    else:
        comma_parts = [normalize_text(part) for part in normalized.split(",", maxsplit=1) if normalize_text(part)]
        if len(comma_parts) != 2:
            return None
        left, right = comma_parts

    right = normalize_text(
        re.split(r"\b(expected|graduation|abschluss|since|from)\b", right, maxsplit=1, flags=re.IGNORECASE)[0]
    )

    if _looks_like_degree_text(left):
        degree = left
        institution = right
    elif _looks_like_degree_text(right):
        degree = right
        institution = left
    else:
        return None

    if len(degree) > 120 or len(institution) > 120:
        return None
    if _looks_like_narrative_line(degree) or _looks_like_narrative_line(institution):
        return None

    start_date, end_date = _extract_date_range(normalized)
    if start_date is None:
        year_match = _YEAR_PATTERN.search(normalized)
        start_date = f"{year_match.group(0)}-01-01" if year_match else None

    return ImportedEducationDraft(
        institution=institution,
        degree=degree,
        start_date=start_date,
        end_date=end_date,
        source_locator=source_locator,
        source_excerpt=normalized,
    )


def _looks_like_degree_text(value: str) -> bool:
    """Return whether one text candidate likely represents degree text."""

    lowered = value.lower()
    collapsed = lowered.replace(".", "")
    markers = tuple(marker.replace(".", "") for marker in _DEGREE_MARKERS)
    return any(re.search(rf"\b{re.escape(marker)}\b", collapsed) for marker in markers)


def _parse_skill_line(line: str, source_locator: str | None) -> list[ImportedSkillDraft]:
    """Parse one skills-section line into skill rows."""

    cleaned_line = normalize_text(line)
    if not cleaned_line:
        return []

    normalized_for_prefix = re.sub(r"^(skills|technologies|tools|kompetenzen|kenntnisse)\s*[:|-]\s*", "", cleaned_line, flags=re.IGNORECASE)
    if not normalized_for_prefix:
        return []

    tokens: list[str]
    if _SKILLS_SPLIT_PATTERN.search(normalized_for_prefix) is None:
        tokens = [normalized_for_prefix]
    else:
        tokens = [part for part in _SKILLS_SPLIT_PATTERN.split(normalized_for_prefix) if part.strip()]

    skills: list[ImportedSkillDraft] = []
    for token in tokens:
        cleaned = _normalize_skill_token(normalize_text(token))
        if _is_valid_skill_token(cleaned):
            skills.append(ImportedSkillDraft(skill_name=cleaned, source_locator=source_locator, source_excerpt=cleaned_line))
            continue

        # Fallback: recover known skill keywords from dense tokens.
        lowered = cleaned.lower()
        for keyword, label in _SKILL_KEYWORDS.items():
            if keyword in lowered:
                skills.append(ImportedSkillDraft(skill_name=label, source_locator=source_locator, source_excerpt=cleaned_line))

    return _deduplicate_skills(skills)


def _normalize_skill_token(token: str) -> str:
    """Normalize extracted skill token into canonical value."""

    lowered = token.lower()
    if lowered in {"llms", "large language models", "large language model"}:
        return "LLM"
    if lowered in {"vlms", "vision language models", "vision language model"}:
        return "VLM"
    if lowered == "mlops":
        return "MLOps"
    if lowered in {"ci/cd", "ci-cd"}:
        return "CI/CD"
    if lowered in {"nlp/understanding", "nlp understanding"}:
        return "NLP"
    if lowered == "computer-vision":
        return "Computer Vision"
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
        "publication",
        "blog",
        "cv",
        "linkedin",
        "toggle menu",
        "follow",
        "email",
        "germany",
        "overview",
        "impact",
        "tech",
        "tooling",
        "capstone",
    }:
        return False

    if lowered.startswith(("view ", "download cv", "skills at a glance", "what i did")):
        return False

    if token.startswith(("-", "•", "*", "·")):
        return False

    if any(part in lowered for part in ("currently", "working", "selected", "follow", "portfolio", "at a glance")):
        return False

    if "." in token:
        return False

    if len(token.split()) == 1 and token == lowered and lowered not in _SKILL_KEYWORDS and lowered not in {"mlops", "ci/cd"}:
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
    has_separator = any(separator in lowered for separator in _EXPERIENCE_SEPARATORS) or any(
        separator in line for separator in _EXPERIENCE_DASH_SEPARATORS
    )
    if not has_separator:
        return False

    parsed = _parse_experience_line(line, source_locator=None)
    if parsed is None:
        return False

    if _company_hint_score(parsed.company) > 0:
        return True
    return _contains_role_keyword(parsed.title)


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
