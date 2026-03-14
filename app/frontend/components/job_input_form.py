"""Job intake input form component."""

from __future__ import annotations

from nicegui import ui

from app.frontend.state.job_state import JobState
from app.frontend.utils.labels import LANGUAGE_OPTIONS


def render_job_input_form(job_state: JobState) -> None:
    """Render job intake inputs.

    Args:
        job_state: Mutable job workflow state.

    Returns:
        None.
    """

    with ui.card().classes("w-full"):
        ui.label("Target Job Input").classes("text-md font-semibold")

        ui.input(
            "Job Title",
            value=job_state.intake.title,
            on_change=lambda event: _set_title(job_state, str(event.value)),
        )
        ui.input(
            "Company Name",
            value=job_state.intake.company or "",
            on_change=lambda event: _set_company(job_state, str(event.value)),
        )
        ui.input(
            "Job URL",
            value=job_state.intake.job_url or "",
            on_change=lambda event: _set_job_url(job_state, str(event.value)),
        )
        ui.textarea(
            "Job Description",
            value=job_state.intake.description,
            on_change=lambda event: _set_description(job_state, str(event.value)),
        ).props("autogrow")

        ui.select(
            options={code: label for label, code in LANGUAGE_OPTIONS},
            value=job_state.intake.language,
            label="Target Language",
            on_change=lambda event: _set_language(job_state, str(event.value)),
        )
        ui.switch(
            "Use LLM-assisted analysis",
            value=job_state.intake.use_llm_analysis,
            on_change=lambda event: _set_use_llm_analysis(job_state, bool(event.value)),
        )
        ui.textarea(
            "Optional Notes",
            value=job_state.intake.notes or "",
            on_change=lambda event: _set_notes(job_state, str(event.value)),
        ).props("autogrow")


def _set_title(job_state: JobState, value: str) -> None:
    """Set job title field."""

    job_state.intake.title = value


def _set_company(job_state: JobState, value: str) -> None:
    """Set company name field."""

    job_state.intake.company = value or None


def _set_job_url(job_state: JobState, value: str) -> None:
    """Set job URL field."""

    job_state.intake.job_url = value or None


def _set_description(job_state: JobState, value: str) -> None:
    """Set job description field."""

    job_state.intake.description = value


def _set_language(job_state: JobState, value: str) -> None:
    """Set target language field."""

    job_state.intake.language = value or "en"


def _set_use_llm_analysis(job_state: JobState, value: bool) -> None:
    """Set optional LLM analysis toggle field."""

    job_state.intake.use_llm_analysis = value


def _set_notes(job_state: JobState, value: str) -> None:
    """Set optional job notes field."""

    job_state.intake.notes = value or None
