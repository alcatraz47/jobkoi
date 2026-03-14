"""Navigation components for the Jobkoi frontend."""

from __future__ import annotations

from nicegui import ui


def render_navigation() -> None:
    """Render top navigation links for frontend pages.

    Returns:
        None.
    """

    with ui.header().classes("items-center justify-between bg-slate-800 text-white"):
        ui.label("Jobkoi").classes("text-lg font-semibold")
        with ui.row().classes("gap-2"):
            ui.link("Dashboard", "/").classes("text-white")
            ui.link("Profile", "/profile").classes("text-white")
            ui.link("Job Intake", "/job-intake").classes("text-white")
            ui.link("Match Review", "/match-review").classes("text-white")
            ui.link("Output Review", "/output-review").classes("text-white")
            ui.link("Packages", "/application-packages").classes("text-white")
