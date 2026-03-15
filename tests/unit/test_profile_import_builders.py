"""Unit tests for profile import domain builders."""

from __future__ import annotations

from app.domain.profile_import_builders import (
    build_imported_profile_from_text,
    detect_import_language,
    flatten_imported_profile_to_fields,
)


def test_build_imported_profile_from_text_extracts_core_fields() -> None:
    """Builder should extract core profile signals from CV-style text."""

    text = """
    Arfan Example
    Senior Backend Engineer
    arfan@example.com
    +49 123 456789

    Experience
    Software Engineer at Example GmbH

    Education
    MSc Computer Science at TU Berlin

    Skills
    Python, FastAPI, SQL
    """

    draft = build_imported_profile_from_text(text=text, source_locator="resume.pdf")

    assert draft.full_name == "Arfan Example"
    assert draft.email == "arfan@example.com"
    assert draft.phone is not None
    assert draft.experiences
    assert draft.educations
    assert [item.skill_name for item in draft.skills] == ["Python", "FastAPI", "SQL"]


def test_build_imported_profile_from_text_handles_website_style_content() -> None:
    """Builder should parse useful data from website-style multi-line content."""

    text = """
    Md Mahmudul Haque
    AI Engineer • Computer Vision • NLP • LLMs/VLMs
    Skills AI Engineering • Computer Vision • NLP • LLMs/VLMs
    I am currently working at Fraunhofer IML, delivering computer vision and OCR solutions.
    """

    draft = build_imported_profile_from_text(text=text, source_locator="https://portfolio.example.dev")

    assert draft.full_name == "Md Mahmudul Haque"
    assert draft.headline is not None
    assert any(skill.skill_name == "Computer Vision" for skill in draft.skills)
    assert any(skill.skill_name == "NLP" for skill in draft.skills)


def test_phone_extraction_ignores_isbn_numbers() -> None:
    """Builder should avoid mapping ISBN-like values as phone numbers."""

    text = """
    Arfan Example
    ISBN 978-981-15-8354-4
    Contact +49 176 1234567
    """

    draft = build_imported_profile_from_text(text=text, source_locator="resume.pdf")

    assert draft.phone == "+49 176 1234567"


def test_flatten_imported_profile_to_fields_emits_ordered_paths() -> None:
    """Flattening should produce deterministic field paths for review workflows."""

    text = """
    Arfan Example
    arfan@example.com

    Experience
    Software Engineer at Example GmbH

    Skills
    Python, Docker
    """

    draft = build_imported_profile_from_text(text=text, source_locator="resume.docx")
    rows = flatten_imported_profile_to_fields(draft)

    assert rows
    assert rows[0].sort_order == 0
    assert any(item.field_path == "full_name" for item in rows)
    assert any(item.field_path == "email" for item in rows)
    assert any(item.field_path.startswith("experiences[") for item in rows)
    assert any(item.field_path.startswith("skills[") for item in rows)


def test_detect_import_language_falls_back_to_en_or_de() -> None:
    """Language detection should return supported fallback language labels."""

    assert detect_import_language("Ich habe Erfahrung mit Python und Docker.") in {"en", "de"}
    assert detect_import_language("I build APIs with FastAPI and SQLAlchemy.") in {"en", "de"}


def test_builder_parses_company_name_containing_analytics() -> None:
    """Builder should parse experience rows even when company includes Analytics."""

    text_input = """
    Mina Carter
    Data Engineer
    mina.carter@example.com

    Experience
    Data Engineer at Northwind Analytics
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.experiences
    assert draft.experiences[0].company == "Northwind Analytics"
    assert draft.experiences[0].title == "Data Engineer"


def test_builder_keeps_ci_cd_as_single_skill() -> None:
    """Skills parser should keep CI/CD as one canonical skill token."""

    text_input = """
    Victor Stone

    Skills
    Docker, Kubernetes, Python, CI/CD
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")
    names = [item.skill_name for item in draft.skills]

    assert "CI/CD" in names


def test_builder_avoids_false_inline_experience_matches_from_word_fragments() -> None:
    """Inline experience detection should not trigger on generic prose containing 'at'."""

    text_input = """
    Arfan Example
    Building data platforms and automation systems at scale for logistics teams.
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.experiences == []



def test_builder_does_not_map_education_line_to_location_and_uses_contact_location() -> None:
    """Builder should map contact-line city as location and avoid education scalar leakage."""

    text_input = """
    Md Mahmudul Haque
    +49 176 32925096 | Dortmund, Germany
    Master of Data Science, Carl von Ossietzky University Oldenburg Expected: Summer 2027
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.location == "Dortmund, Germany"
    assert draft.location != "Master of Data Science, Carl von Ossietzky University Oldenburg Expected: Summer 2027"


def test_builder_extracts_inline_education_from_degree_comma_line() -> None:
    """Builder should parse comma-formatted degree/institution lines without education heading."""

    text_input = """
    Md Mahmudul Haque
    AI Engineer
    Master of Data Science, Carl von Ossietzky University Oldenburg Expected: Summer 2027
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.educations
    assert draft.educations[0].degree == "Master of Data Science"
    assert draft.educations[0].institution == "Carl von Ossietzky University Oldenburg"
    assert draft.headline == "AI Engineer"


def test_builder_does_not_use_present_as_company_value() -> None:
    """Experience parser should not map temporal status tokens into company fields."""

    text_input = """
    Experience
    Data Science Working Student 2025 - Present Fraunhofer IML
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.experiences
    assert draft.experiences[0].company == "Fraunhofer IML"
    assert draft.experiences[0].title == "Data Science Working Student"


def test_builder_cleans_present_experience_title_and_company_address() -> None:
    """Builder should clean temporal suffixes and address tails in experience tuples."""

    text_input = """
    Experience
    Data Science Working Student May 2025 - Present Fraunhofer IML Joseph-von-Fraunhofer-Str. 2-4, 44227 Dortmund, Germany
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.experiences
    assert draft.experiences[0].title == "Data Science Working Student"
    assert draft.experiences[0].company == "Fraunhofer IML"


def test_builder_parses_role_pattern_into_company_and_title() -> None:
    """Builder should parse lines with explicit role markers."""

    text_input = """
    Experience
    HT Ventures (January 2025-Present) Role: AI Engineer (Remote) Location: Hamburg, Germany - Architected support copilot workflows.
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.experiences
    assert draft.experiences[0].company == "HT Ventures"
    assert draft.experiences[0].title == "AI Engineer (Remote)"



def test_builder_splits_multi_entry_experience_section_into_multiple_roles() -> None:
    """Experience section parser should split consecutive roles into separate entries."""

    text_input = """
    EXPERIENCE
    Data Science Working Student May 2025 - Present
    Fraunhofer IML Joseph-von-Fraunhofer-Str. 2-4, 44227 Dortmund, Germany
    • Built railway transportation analytics solutions.
    Data Science Intern / Working Student April 2024 - April 2025
    Henkel AG & Co. KGaA 40191 Dusseldorf, Germany
    • Built data workflows and sustainability NLP solutions.
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert len(draft.experiences) >= 2
    assert draft.experiences[0].company == "Fraunhofer IML"
    assert draft.experiences[0].title == "Data Science Working Student"
    assert draft.experiences[1].company == "Henkel AG & Co. KGaA"
    assert draft.experiences[1].title == "Data Science Intern / Working Student"



def test_builder_parses_company_date_header_with_following_role_line() -> None:
    """Experience parser should combine company/date header with following role line."""

    text_input = """
    Experience
    HT Ventures (January 2025-Present)
    Role: AI Engineer (Remote)
    Location: Hamburg, Germany
    - Built support copilot workflows.
    Fraunhofer IML (May 2025-Present)
    - Built railway computer vision systems.
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="https://portfolio.example.dev/experience/")

    assert len(draft.experiences) >= 2
    assert draft.experiences[0].company == "HT Ventures"
    assert draft.experiences[0].title == "AI Engineer (Remote)"
    assert draft.experiences[1].company == "Fraunhofer IML"


def test_builder_skips_contact_handles_when_extracting_name_and_headline() -> None:
    """Builder should ignore social/contact handle lines before name and headline extraction."""

    text_input = """
    linkedin:md-mahmudul-haque | github:alcatraz47
    Md Mahmudul Haque
    AI Engineer • Computer Vision • NLP • LLMs/VLMs
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="resume.pdf")

    assert draft.full_name == "Md Mahmudul Haque"
    assert draft.headline == "AI Engineer • Computer Vision • NLP • LLMs/VLMs"



def test_phone_extraction_ignores_numeric_fragments_inside_urls() -> None:
    """Builder should not map numeric URL fragments into phone fields."""

    text_input = """
    Publications
    https://www.researchgate.net/publication/336639606Krishok-An_IoT_Based_Intelligent_Farming_Solution
    Md Mahmudul Haque
    arfan@example.com
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="https://portfolio.example.dev")

    assert draft.phone is None



def test_builder_keeps_partial_experience_when_company_is_known_but_title_is_missing() -> None:
    """Experience parser should keep company/date entries even when role title is not explicit."""

    text_input = """
    Experience
    Fraunhofer IML (May 2025-Present)
    - Built railway computer vision systems.
    """

    draft = build_imported_profile_from_text(text=text_input, source_locator="https://portfolio.example.dev/experience/")
    rows = flatten_imported_profile_to_fields(draft)

    assert draft.experiences
    assert draft.experiences[0].company == "Fraunhofer IML"
    assert draft.experiences[0].title == ""
    assert any(item.field_path == "experiences[0].title" and item.suggested_value == "" for item in rows)
