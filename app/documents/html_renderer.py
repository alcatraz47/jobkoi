"""HTML renderers for ATS-friendly CV and cover letter templates."""

from __future__ import annotations

from typing import Any

from app.documents.template_renderer import render_html_template

_CV_TEMPLATES: dict[str, str] = {
    "en": "cv_en.j2",
    "de": "cv_de.j2",
}

_COVER_LETTER_TEMPLATES: dict[str, str] = {
    "en": "cover_letter_en.j2",
    "de": "cover_letter_de.j2",
}


class DocumentRenderError(ValueError):
    """Raised when an unsupported document language is requested."""


def render_cv_html(*, language: str, context: dict[str, Any]) -> str:
    """Render ATS-friendly CV HTML.

    Args:
        language: Target language code.
        context: Render context dictionary.

    Returns:
        Rendered CV HTML string.

    Raises:
        DocumentRenderError: If language is not supported.
    """

    template_name = _CV_TEMPLATES.get(language)
    if template_name is None:
        raise DocumentRenderError(f"Unsupported CV language: {language}")
    return render_html_template(template_name, context)


def render_cover_letter_html(*, language: str, context: dict[str, Any]) -> str:
    """Render cover letter HTML.

    Args:
        language: Target language code.
        context: Render context dictionary.

    Returns:
        Rendered cover letter HTML string.

    Raises:
        DocumentRenderError: If language is not supported.
    """

    template_name = _COVER_LETTER_TEMPLATES.get(language)
    if template_name is None:
        raise DocumentRenderError(f"Unsupported cover letter language: {language}")
    return render_html_template(template_name, context)
