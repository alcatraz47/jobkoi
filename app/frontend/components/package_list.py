"""Application package list component."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from app.frontend.utils.formatting import format_datetime


def render_package_list(
    *,
    packages: list[dict[str, Any]],
    on_open: Callable[[str], None],
) -> None:
    """Render package list cards with open actions.

    Args:
        packages: Package payload list.
        on_open: Callback receiving package identifier.

    Returns:
        None.
    """

    with ui.column().classes("w-full"):
        if not packages:
            ui.label("No application packages stored yet.").classes("text-sm text-slate-600")
            return

        for package in packages:
            package_id = str(package.get("id", ""))
            with ui.card().classes("w-full"):
                ui.label(
                    f"{package.get('language', '-').upper()} • {package.get('status', '-')}")
                ui.label(f"Created: {format_datetime(package.get('created_at'))}").classes("text-xs text-slate-500")
                ui.label(f"Job Post: {package.get('job_post_id', '-')}").classes("text-xs")
                ui.button("Open Package", on_click=lambda _, p=package_id: on_open(p)).props("flat")
