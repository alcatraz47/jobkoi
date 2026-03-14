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
