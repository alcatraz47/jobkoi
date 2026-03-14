"""Unit tests for text normalization and language detection helpers."""

from __future__ import annotations

from app.domain.job_text import detect_language_fallback, normalize_text, split_candidate_lines


def test_normalize_text_removes_control_characters_and_whitespace() -> None:
    """Text normalization should strip controls and compact whitespace."""

    raw = " Senior\x0b Python   Engineer\n\nwith   APIs "
    assert normalize_text(raw) == "Senior Python Engineer with APIs"


def test_split_candidate_lines_preserves_meaningful_lines() -> None:
    """Candidate line splitting should produce deterministic line segments."""

    text = "Must have Python. Nice to have Rust; Work with APIs\nCollaborate with team"
    lines = split_candidate_lines(text)

    assert lines == [
        "Must have Python",
        "Nice to have Rust",
        "Work with APIs",
        "Collaborate with team",
    ]


def test_detect_language_fallback_handles_english_and_german() -> None:
    """Language fallback should classify both English and German examples."""

    english = "Must have Python experience and strong communication skills."
    german = "Erfahrung mit Python ist erforderlich und Deutschkenntnisse sind von Vorteil."

    assert detect_language_fallback(english) == "en"
    assert detect_language_fallback(german) == "de"
