"""Composed profile editor form sections."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.components.academic_achievement_form import render_academic_achievement_form
from app.frontend.components.certification_form import render_certification_form
from app.frontend.components.education_form import render_education_form
from app.frontend.components.experience_form import render_experience_form
from app.frontend.components.language_form import render_language_form
from app.frontend.components.project_form import render_project_form
from app.frontend.components.skill_form import render_skill_form
from app.frontend.state.profile_state import JobPreferenceEntry, ProfileState


def render_profile_forms(profile_state: ProfileState) -> None:
    """Render the complete master profile editor form.

    Args:
        profile_state: Mutable profile state used by form controls.

    Returns:
        None.
    """

    _render_personal_information(profile_state)

    with ui.expansion("Work Experience", icon="work", value=True).classes("w-full"):
        render_experience_form(profile_state)

    with ui.expansion("Skills", icon="tune", value=True).classes("w-full"):
        render_skill_form(profile_state)

    with ui.expansion("Education", icon="school", value=True).classes("w-full"):
        render_education_form(profile_state)

    with ui.expansion("Academic Achievements", icon="emoji_events", value=True).classes("w-full"):
        render_academic_achievement_form(profile_state)

    with ui.expansion("Projects", icon="inventory", value=False).classes("w-full"):
        render_project_form(profile_state)

    with ui.expansion("Certifications", icon="verified", value=False).classes("w-full"):
        render_certification_form(profile_state)

    with ui.expansion("Languages", icon="translate", value=False).classes("w-full"):
        render_language_form(profile_state)

    with ui.expansion("Job Preferences", icon="travel_explore", value=False).classes("w-full"):
        _render_job_preference_form(profile_state)


def _render_personal_information(profile_state: ProfileState) -> None:
    """Render personal and summary information fields."""

    with ui.card().classes("w-full"):
        ui.label("Personal Information").classes("text-md font-semibold")
        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.input(
                "Full Name",
                value=profile_state.draft.full_name,
                on_change=lambda event: _set_full_name(profile_state, str(event.value)),
            )
            ui.input(
                "Email",
                value=profile_state.draft.email,
                on_change=lambda event: _set_email(profile_state, str(event.value)),
            )
            ui.input(
                "Phone",
                value=profile_state.draft.phone or "",
                on_change=lambda event: _set_phone(profile_state, str(event.value)),
            )
            ui.input(
                "Location",
                value=profile_state.draft.location or "",
                on_change=lambda event: _set_location(profile_state, str(event.value)),
            )
            ui.input(
                "Professional Headline",
                value=profile_state.draft.headline or "",
                on_change=lambda event: _set_headline(profile_state, str(event.value)),
            ).classes("col-span-2")
            ui.textarea(
                "Professional Summary",
                value=profile_state.draft.summary or "",
                on_change=lambda event: _set_summary(profile_state, str(event.value)),
            ).props("autogrow").classes("col-span-2")


def _render_job_preference_form(profile_state: ProfileState) -> None:
    """Render job preference rows for local profile preferences."""

    ui.label("Job Preferences").classes("text-md font-semibold")
    ui.label(
        "Job preferences are stored in the frontend context for planning and guidance."
    ).classes("text-xs text-slate-500")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        """Repaint job preference rows."""

        container.clear()
        with container:
            if not profile_state.draft.job_preferences:
                ui.label("No job preferences added yet.").classes("text-sm text-slate-500")
            for index, _ in enumerate(profile_state.draft.job_preferences):
                _render_job_preference_card(profile_state, index, refresh)

    ui.button(
        "Add Job Preference",
        on_click=lambda: _add_job_preference(profile_state, refresh),
    ).props("outline")
    refresh()


def _render_job_preference_card(
    profile_state: ProfileState,
    index: int,
    refresh: Callable[[], None],
) -> None:
    """Render one editable job preference card."""

    item = profile_state.draft.job_preferences[index]
    with ui.card().classes("w-full"):
        ui.input(
            "Preferred Titles",
            value=item.preferred_titles or "",
            on_change=lambda event, i=index: _set_preferred_titles(
                profile_state,
                i,
                str(event.value),
            ),
        )
        ui.input(
            "Preferred Locations",
            value=item.preferred_locations or "",
            on_change=lambda event, i=index: _set_preferred_locations(
                profile_state,
                i,
                str(event.value),
            ),
        )
        ui.select(
            options=["remote", "hybrid", "onsite", "flexible"],
            value=item.work_mode or "",
            label="Work Mode",
            on_change=lambda event, i=index: _set_work_mode(
                profile_state,
                i,
                str(event.value),
            ),
        )
        ui.button(
            "Delete",
            on_click=lambda _, i=index: _delete_job_preference(profile_state, i, refresh),
        ).props("flat color=negative")


def _add_job_preference(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append an empty job preference row."""

    profile_state.draft.job_preferences.append(JobPreferenceEntry())
    refresh()


def _delete_job_preference(
    profile_state: ProfileState,
    index: int,
    refresh: Callable[[], None],
) -> None:
    """Delete a job preference row by index."""

    del profile_state.draft.job_preferences[index]
    refresh()


def _set_full_name(profile_state: ProfileState, value: str) -> None:
    """Set full-name field in draft state."""

    profile_state.draft.full_name = value


def _set_email(profile_state: ProfileState, value: str) -> None:
    """Set email field in draft state."""

    profile_state.draft.email = value


def _set_phone(profile_state: ProfileState, value: str) -> None:
    """Set phone field in draft state."""

    profile_state.draft.phone = value or None


def _set_location(profile_state: ProfileState, value: str) -> None:
    """Set location field in draft state."""

    profile_state.draft.location = value or None


def _set_headline(profile_state: ProfileState, value: str) -> None:
    """Set headline field in draft state."""

    profile_state.draft.headline = value or None


def _set_summary(profile_state: ProfileState, value: str) -> None:
    """Set summary field in draft state."""

    profile_state.draft.summary = value or None


def _set_preferred_titles(profile_state: ProfileState, index: int, value: str) -> None:
    """Set preferred titles field."""

    profile_state.draft.job_preferences[index].preferred_titles = value or None


def _set_preferred_locations(profile_state: ProfileState, index: int, value: str) -> None:
    """Set preferred locations field."""

    profile_state.draft.job_preferences[index].preferred_locations = value or None


def _set_work_mode(profile_state: ProfileState, index: int, value: str) -> None:
    """Set preferred work mode field."""

    profile_state.draft.job_preferences[index].work_mode = value or None
