"""Snapshot tests for rendered CV HTML templates."""

from __future__ import annotations

import re
from pathlib import Path

from app.documents.html_renderer import render_cv_html


def test_rendered_cv_html_matches_snapshot() -> None:
    """Rendered English CV HTML should match the saved snapshot."""

    context = {
        "full_name": "Arfan Example",
        "email": "arfan@example.com",
        "phone": "+49 123 4567",
        "location": "Berlin",
        "headline": "Backend Engineer",
        "summary": "Python engineer focused on APIs.",
        "experiences": [
            {
                "company": "Example GmbH",
                "title": "Software Engineer",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "description": "Built Python and FastAPI services.",
            }
        ],
        "educations": [
            {
                "institution": "TU Example",
                "degree": "MSc",
                "field_of_study": "Computer Science",
                "start_date": "2018-01-01",
                "end_date": "2020-01-01",
            }
        ],
        "skills": [
            {"skill_name": "Python", "level": "advanced", "category": "programming"},
            {"skill_name": "FastAPI", "level": "advanced", "category": "backend"},
        ],
    }

    rendered = render_cv_html(language="en", context=context)

    snapshot_path = Path("tests/snapshots/cv_en_snapshot.html")
    expected = snapshot_path.read_text(encoding="utf-8")

    assert _normalize_html(rendered) == _normalize_html(expected)


def _normalize_html(html_text: str) -> str:
    """Normalize HTML for stable snapshot comparison.

    Args:
        html_text: Raw HTML text.

    Returns:
        Normalized HTML token string.
    """

    collapsed = re.sub(r"\s+", " ", html_text).strip()
    return collapsed
