"""Language proficiency section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import LanguageProficiencyEntry, ProfileState


def render_language_form(profile_state: ProfileState) -> None:
    """Render editable language proficiency list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Languages").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.languages:
                ui.label("No languages added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.languages):
                _render_language_card(profile_state, index, item, refresh)

    ui.button("Add Language", on_click=lambda: _add_language(profile_state, refresh)).props("outline")
    refresh()


def _render_language_card(
    profile_state: ProfileState,
    index: int,
    item: LanguageProficiencyEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one language item card."""

    with ui.card().classes("w-full"):
        ui.input("Language", value=item.language, on_change=lambda e, i=index: _set_language(profile_state, i, e.value)).classes("w-full")
        ui.input(
            "Proficiency",
            value=item.proficiency,
            on_change=lambda e, i=index: _set_proficiency(profile_state, i, e.value),
        ).classes("w-full")
        ui.button("Delete", on_click=lambda _, i=index: _delete_language(profile_state, i, refresh)).props("flat color=negative")


def _add_language(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty language item."""

    profile_state.draft.languages.append(LanguageProficiencyEntry())
    refresh()


def _delete_language(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one language item by index."""

    del profile_state.draft.languages[index]
    refresh()


def _set_language(profile_state: ProfileState, index: int, value: str) -> None:
    """Set language field."""

    profile_state.draft.languages[index].language = value


def _set_proficiency(profile_state: ProfileState, index: int, value: str) -> None:
    """Set proficiency field."""

    profile_state.draft.languages[index].proficiency = value
