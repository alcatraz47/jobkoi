"""Project section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import ProfileState, ProjectEntry


def render_project_form(profile_state: ProfileState) -> None:
    """Render editable project list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Projects").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.projects:
                ui.label("No projects added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.projects):
                _render_project_card(profile_state, index, item, refresh)

    ui.button("Add Project", on_click=lambda: _add_project(profile_state, refresh)).props("outline")
    refresh()


def _render_project_card(
    profile_state: ProfileState,
    index: int,
    item: ProjectEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one project item card."""

    with ui.card().classes("w-full"):
        ui.input("Project Name", value=item.name, on_change=lambda e, i=index: _set_name(profile_state, i, e.value)).classes("w-full")
        ui.input("Role", value=item.role or "", on_change=lambda e, i=index: _set_role(profile_state, i, e.value)).classes("w-full")
        ui.input(
            "Technologies",
            value=item.technologies or "",
            on_change=lambda e, i=index: _set_technologies(profile_state, i, e.value),
        ).classes("w-full")
        ui.textarea(
            "Description",
            value=item.description or "",
            on_change=lambda e, i=index: _set_description(profile_state, i, e.value),
        ).props("autogrow").classes("w-full")
        ui.textarea(
            "Outcome",
            value=item.outcome or "",
            on_change=lambda e, i=index: _set_outcome(profile_state, i, e.value),
        ).props("autogrow").classes("w-full")
        ui.button("Delete", on_click=lambda _, i=index: _delete_project(profile_state, i, refresh)).props("flat color=negative")


def _add_project(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty project item."""

    profile_state.draft.projects.append(ProjectEntry())
    refresh()


def _delete_project(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one project item by index."""

    del profile_state.draft.projects[index]
    refresh()


def _set_name(profile_state: ProfileState, index: int, value: str) -> None:
    """Set project name."""

    profile_state.draft.projects[index].name = value


def _set_role(profile_state: ProfileState, index: int, value: str) -> None:
    """Set project role."""

    profile_state.draft.projects[index].role = value or None


def _set_technologies(profile_state: ProfileState, index: int, value: str) -> None:
    """Set project technologies."""

    profile_state.draft.projects[index].technologies = value or None


def _set_description(profile_state: ProfileState, index: int, value: str) -> None:
    """Set project description."""

    profile_state.draft.projects[index].description = value or None


def _set_outcome(profile_state: ProfileState, index: int, value: str) -> None:
    """Set project outcome."""

    profile_state.draft.projects[index].outcome = value or None
