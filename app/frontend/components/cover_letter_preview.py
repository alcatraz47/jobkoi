"""Cover letter preview component for output review page."""

from __future__ import annotations

from nicegui import ui


def render_cover_letter_preview(
    content_text: str,
    evidence_refs: list[str],
    *,
    html_preview: str | None = None,
) -> None:
    """Render cover letter preview panel.

    Args:
        content_text: Generated or selected cover letter text.
        evidence_refs: Source evidence references.
        html_preview: Optional rendered cover-letter HTML content.

    Returns:
        None.
    """

    with ui.card().classes("w-full"):
        ui.label("Tailored Cover Letter Preview").classes("text-md font-semibold")
        if html_preview:
            ui.html(html_preview).classes("w-full text-sm")
        else:
            ui.label(content_text or "No cover letter content generated yet.").classes(
                "text-sm whitespace-pre-wrap"
            )

        ui.separator()
        ui.label("Evidence references").classes("text-sm font-semibold")
        if not evidence_refs:
            ui.label("No evidence references available.").classes("text-sm text-slate-600")
            return
        for item in evidence_refs:
            ui.label(f"- {item}").classes("text-sm")
