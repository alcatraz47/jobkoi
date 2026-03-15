"""Academic achievement section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import AcademicAchievementEntry, ProfileState


def render_academic_achievement_form(profile_state: ProfileState) -> None:
    """Render editable academic achievement list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Academic Achievements").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.academic_achievements:
                ui.label("No academic achievements added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.academic_achievements):
                _render_achievement_card(profile_state, index, item, refresh)

    ui.button("Add Academic Achievement", on_click=lambda: _add_achievement(profile_state, refresh)).props("outline")
    refresh()


def _render_achievement_card(
    profile_state: ProfileState,
    index: int,
    item: AcademicAchievementEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one academic achievement card."""

    with ui.card().classes("w-full"):
        ui.input("Title", value=item.title, on_change=lambda e, i=index: _set_title(profile_state, i, e.value)).classes("w-full")
        ui.input(
            "Type (award/publication/thesis/research/etc.)",
            value=item.achievement_type,
            on_change=lambda e, i=index: _set_type(profile_state, i, e.value),
        ).classes("w-full")
        ui.input(
            "Institution",
            value=item.institution or "",
            on_change=lambda e, i=index: _set_institution(profile_state, i, e.value),
        ).classes("w-full")
        ui.input("Year", value=item.year or "", on_change=lambda e, i=index: _set_year(profile_state, i, e.value)).classes("w-full")
        ui.textarea(
            "Description",
            value=item.description or "",
            on_change=lambda e, i=index: _set_description(profile_state, i, e.value),
        ).props("autogrow").classes("w-full")
        ui.button("Delete", on_click=lambda _, i=index: _delete_achievement(profile_state, i, refresh)).props("flat color=negative")


def _add_achievement(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty academic achievement item."""

    profile_state.draft.academic_achievements.append(AcademicAchievementEntry())
    refresh()


def _delete_achievement(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one achievement item by index."""

    del profile_state.draft.academic_achievements[index]
    refresh()


def _set_title(profile_state: ProfileState, index: int, value: str) -> None:
    """Set academic achievement title."""

    profile_state.draft.academic_achievements[index].title = value


def _set_type(profile_state: ProfileState, index: int, value: str) -> None:
    """Set academic achievement type."""

    profile_state.draft.academic_achievements[index].achievement_type = value


def _set_institution(profile_state: ProfileState, index: int, value: str) -> None:
    """Set academic achievement institution."""

    profile_state.draft.academic_achievements[index].institution = value or None


def _set_year(profile_state: ProfileState, index: int, value: str) -> None:
    """Set academic achievement year."""

    profile_state.draft.academic_achievements[index].year = value or None


def _set_description(profile_state: ProfileState, index: int, value: str) -> None:
    """Set academic achievement description."""

    profile_state.draft.academic_achievements[index].description = value or None
