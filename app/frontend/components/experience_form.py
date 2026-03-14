"""Experience section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import ExperienceEntry, ProfileState


def render_experience_form(profile_state: ProfileState) -> None:
    """Render editable experience list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Work Experience").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.experiences:
                ui.label("No experiences added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.experiences):
                _render_experience_card(profile_state, index, item, refresh)

    ui.button("Add Experience", on_click=lambda: _add_experience(profile_state, refresh)).props("outline")
    refresh()


def _render_experience_card(
    profile_state: ProfileState,
    index: int,
    item: ExperienceEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one experience entry card."""

    with ui.card().classes("w-full"):
        ui.input(
            "Company",
            value=item.company,
            on_change=lambda event, i=index: _set_company(profile_state, i, str(event.value)),
        )
        ui.input(
            "Title",
            value=item.title,
            on_change=lambda event, i=index: _set_title(profile_state, i, str(event.value)),
        )
        ui.input(
            "Start Date (YYYY-MM-DD)",
            value=item.start_date or "",
            on_change=lambda event, i=index: _set_start_date(profile_state, i, str(event.value)),
        )
        ui.input(
            "End Date (YYYY-MM-DD)",
            value=item.end_date or "",
            on_change=lambda event, i=index: _set_end_date(profile_state, i, str(event.value)),
        )
        ui.textarea(
            "Description",
            value=item.description or "",
            on_change=lambda event, i=index: _set_description(profile_state, i, str(event.value)),
        ).props("autogrow")
        ui.button(
            "Delete",
            on_click=lambda _, i=index: _delete_experience(profile_state, i, refresh),
        ).props("flat color=negative")


def _add_experience(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty experience item."""

    profile_state.draft.experiences.append(ExperienceEntry())
    refresh()


def _delete_experience(
    profile_state: ProfileState,
    index: int,
    refresh: Callable[[], None],
) -> None:
    """Delete one experience item by index."""

    del profile_state.draft.experiences[index]
    refresh()


def _set_company(profile_state: ProfileState, index: int, value: str) -> None:
    """Set company field."""

    profile_state.draft.experiences[index].company = value


def _set_title(profile_state: ProfileState, index: int, value: str) -> None:
    """Set title field."""

    profile_state.draft.experiences[index].title = value


def _set_start_date(profile_state: ProfileState, index: int, value: str) -> None:
    """Set start date field."""

    profile_state.draft.experiences[index].start_date = value or None


def _set_end_date(profile_state: ProfileState, index: int, value: str) -> None:
    """Set end date field."""

    profile_state.draft.experiences[index].end_date = value or None


def _set_description(profile_state: ProfileState, index: int, value: str) -> None:
    """Set description field."""

    profile_state.draft.experiences[index].description = value or None
