"""Job intake page for job post submission and analysis kickoff."""

from __future__ import annotations

from dataclasses import asdict

from nicegui import run, ui

from app.frontend.components.job_input_form import render_job_input_form
from app.frontend.components.navigation import render_navigation
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.job_post_api import JobPostApi
from app.frontend.state.job_state import JobState
from app.frontend.state.session_state import FrontendSessionState
from app.frontend.utils.mappers import build_job_post_payload


def register_job_intake_page(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    job_post_api: JobPostApi,
) -> None:
    """Register job intake page route.

    Args:
        job_state: Shared job workflow state.
        session_state: Shared session selection state.
        job_post_api: Job post API adapter.

    Returns:
        None.
    """

    @ui.page("/job-intake")
    async def job_intake_page() -> None:
        """Render job intake page."""

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.label("Job Intake").classes("text-2xl font-semibold")
            ui.label(
                "Paste job details, store a job post, and run deterministic requirement analysis."
            ).classes("text-sm text-slate-600")

            render_job_input_form(job_state)

            async def save_job_action() -> None:
                """Save job-post payload."""

                await _save_job_post(
                    job_state=job_state,
                    session_state=session_state,
                    job_post_api=job_post_api,
                )

            async def analyze_job_action() -> None:
                """Create analysis for selected job post."""

                await _analyze_job_post(
                    job_state=job_state,
                    session_state=session_state,
                    job_post_api=job_post_api,
                )

            with ui.row().classes("gap-3"):
                ui.button("Save Job Post", on_click=save_job_action)
                ui.button("Analyze Job", on_click=analyze_job_action).props("outline")
                ui.button(
                    "Continue to Match Review",
                    on_click=lambda: ui.navigate.to("/match-review"),
                ).props("outline")

            _render_job_context(job_state=job_state, session_state=session_state)


async def _save_job_post(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    job_post_api: JobPostApi,
) -> None:
    """Persist job post and store selected job id."""

    payload = build_job_post_payload(asdict(job_state.intake))
    try:
        response = await run.io_bound(lambda: job_post_api.create_job_post(payload))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    job_state.job_post = response
    session_state.selected_job_post_id = str(response.get("id"))
    session_state.selected_analysis_id = None
    session_state.selected_plan_id = None
    session_state.selected_snapshot_id = None
    session_state.target_language = job_state.intake.language or "en"
    ui.notify("Job post saved.", color="positive")


async def _analyze_job_post(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    job_post_api: JobPostApi,
) -> None:
    """Run analysis for current job post and persist selected analysis id."""

    job_post_id = session_state.selected_job_post_id
    if job_post_id is None:
        await _save_job_post(
            job_state=job_state,
            session_state=session_state,
            job_post_api=job_post_api,
        )
        job_post_id = session_state.selected_job_post_id

    if job_post_id is None:
        return

    try:
        analysis = await run.io_bound(lambda: job_post_api.analyze_job_post(job_post_id, use_llm=False))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    job_state.analysis = analysis
    session_state.selected_analysis_id = str(analysis.get("id"))
    session_state.target_language = job_state.intake.language or "en"
    ui.notify("Job analysis completed.", color="positive")


def _render_job_context(*, job_state: JobState, session_state: FrontendSessionState) -> None:
    """Render selected job and analysis context summary."""

    with ui.card().classes("w-full"):
        ui.label("Current Job Context").classes("text-md font-semibold")
        ui.label(f"Job Post ID: {session_state.selected_job_post_id or '-'}").classes("text-sm")
        ui.label(f"Job Analysis ID: {session_state.selected_analysis_id or '-'}").classes("text-sm")
        ui.label(f"Target language: {session_state.target_language}").classes("text-sm")

        if job_state.analysis is None:
            ui.label("No analysis loaded yet.").classes("text-sm text-slate-600")
            return

        requirements = job_state.analysis.get("requirements", [])
        ui.label(f"Extracted requirements: {len(requirements)}").classes("text-sm")
