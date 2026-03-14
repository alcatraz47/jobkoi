"""Education section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import EducationEntry, ProfileState


def render_education_form(profile_state: ProfileState) -> None:
    """Render editable education list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Education").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.educations:
                ui.label("No educations added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.educations):
                _render_education_card(profile_state, index, item, refresh)

    ui.button("Add Education", on_click=lambda: _add_education(profile_state, refresh)).props("outline")
    refresh()


def _render_education_card(
    profile_state: ProfileState,
    index: int,
    item: EducationEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one education entry card."""

    with ui.card().classes("w-full"):
        ui.input("Institution", value=item.institution, on_change=lambda e, i=index: _set_institution(profile_state, i, e.value))
        ui.input("Degree", value=item.degree, on_change=lambda e, i=index: _set_degree(profile_state, i, e.value))
        ui.input(
            "Field of Study",
            value=item.field_of_study or "",
            on_change=lambda e, i=index: _set_field_of_study(profile_state, i, e.value),
        )
        ui.input(
            "Start Date (YYYY-MM-DD)",
            value=item.start_date or "",
            on_change=lambda e, i=index: _set_start_date(profile_state, i, e.value),
        )
        ui.input(
            "End Date (YYYY-MM-DD)",
            value=item.end_date or "",
            on_change=lambda e, i=index: _set_end_date(profile_state, i, e.value),
        )
        ui.button("Delete", on_click=lambda _, i=index: _delete_education(profile_state, i, refresh)).props("flat color=negative")


def _add_education(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty education item."""

    profile_state.draft.educations.append(EducationEntry())
    refresh()


def _delete_education(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one education item by index."""

    del profile_state.draft.educations[index]
    refresh()


def _set_institution(profile_state: ProfileState, index: int, value: str) -> None:
    """Set institution field."""

    profile_state.draft.educations[index].institution = value


def _set_degree(profile_state: ProfileState, index: int, value: str) -> None:
    """Set degree field."""

    profile_state.draft.educations[index].degree = value


def _set_field_of_study(profile_state: ProfileState, index: int, value: str) -> None:
    """Set field of study field."""

    profile_state.draft.educations[index].field_of_study = value or None


def _set_start_date(profile_state: ProfileState, index: int, value: str) -> None:
    """Set education start date field."""

    profile_state.draft.educations[index].start_date = value or None


def _set_end_date(profile_state: ProfileState, index: int, value: str) -> None:
    """Set education end date field."""

    profile_state.draft.educations[index].end_date = value or None
