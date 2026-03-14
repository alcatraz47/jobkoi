"""Template environment helpers for document rendering."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape


@lru_cache(maxsize=1)
def get_template_environment(template_dir: str | None = None) -> Environment:
    """Return a cached Jinja2 template environment.

    Args:
        template_dir: Optional custom template directory path.

    Returns:
        Cached Jinja2 environment configured for HTML templates.
    """

    if template_dir is None:
        root = Path(__file__).resolve().parents[1]
        template_path = root / "templates"
    else:
        template_path = Path(template_dir)

    loader = FileSystemLoader(str(template_path))
    return Environment(
        loader=loader,
        autoescape=select_autoescape(enabled_extensions=("html", "xml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a named template into HTML.

    Args:
        template_name: Template file name.
        context: Template render context.

    Returns:
        Rendered HTML string.

    Raises:
        TemplateNotFound: If template name is missing from template directory.
    """

    environment = get_template_environment()
    template = environment.get_template(template_name)
    return template.render(**context)
