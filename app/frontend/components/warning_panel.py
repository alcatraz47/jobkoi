"""Warning panel component for truth-constraint messaging."""

from __future__ import annotations

from nicegui import ui


def render_warning_panel(title: str, warnings: list[str]) -> None:
    """Render warning panel with zero-or-more warning messages.

    Args:
        title: Panel title.
        warnings: Warning text list.

    Returns:
        None.
    """

    with ui.card().classes("w-full border-l-4 border-amber-500"):
        ui.label(title).classes("text-md font-semibold text-amber-700")
        if not warnings:
            ui.label("No active warnings.").classes("text-sm text-slate-600")
            return

        for warning in warnings:
            ui.label(f"- {warning}").classes("text-sm text-amber-900")
