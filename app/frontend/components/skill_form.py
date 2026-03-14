"""Skill section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import ProfileState, SkillEntry


def render_skill_form(profile_state: ProfileState) -> None:
    """Render editable skill list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Skills").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.skills:
                ui.label("No skills added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.skills):
                _render_skill_card(profile_state, index, item, refresh)

    ui.button("Add Skill", on_click=lambda: _add_skill(profile_state, refresh)).props("outline")
    refresh()


def _render_skill_card(
    profile_state: ProfileState,
    index: int,
    item: SkillEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one skill item card."""

    with ui.card().classes("w-full"):
        ui.input("Skill", value=item.skill_name, on_change=lambda e, i=index: _set_skill_name(profile_state, i, e.value))
        ui.input("Level", value=item.level or "", on_change=lambda e, i=index: _set_level(profile_state, i, e.value))
        ui.input(
            "Category",
            value=item.category or "",
            on_change=lambda e, i=index: _set_category(profile_state, i, e.value),
        )
        ui.button("Delete", on_click=lambda _, i=index: _delete_skill(profile_state, i, refresh)).props("flat color=negative")


def _add_skill(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty skill item."""

    profile_state.draft.skills.append(SkillEntry())
    refresh()


def _delete_skill(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one skill item by index."""

    del profile_state.draft.skills[index]
    refresh()


def _set_skill_name(profile_state: ProfileState, index: int, value: str) -> None:
    """Set skill name field."""

    profile_state.draft.skills[index].skill_name = value


def _set_level(profile_state: ProfileState, index: int, value: str) -> None:
    """Set skill level field."""

    profile_state.draft.skills[index].level = value or None


def _set_category(profile_state: ProfileState, index: int, value: str) -> None:
    """Set skill category field."""

    profile_state.draft.skills[index].category = value or None
