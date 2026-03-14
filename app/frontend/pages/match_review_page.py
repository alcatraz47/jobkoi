"""Match review page for transparent tailoring evidence inspection."""

from __future__ import annotations

import re
from typing import Any

from nicegui import run, ui

from app.frontend.components.match_summary import render_match_summary
from app.frontend.components.navigation import render_navigation
from app.frontend.components.warning_panel import render_warning_panel
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.job_post_api import JobPostApi
from app.frontend.services.tailoring_api import TailoringApi
from app.frontend.state.job_state import JobState
from app.frontend.state.profile_state import ProfileState
from app.frontend.state.session_state import FrontendSessionState

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9+#.]{2,}")


def register_match_review_page(
    *,
    profile_state: ProfileState,
    job_state: JobState,
    session_state: FrontendSessionState,
    job_post_api: JobPostApi,
    tailoring_api: TailoringApi,
) -> None:
    """Register match review page route.

    Args:
        profile_state: Shared profile state.
        job_state: Shared job state.
        session_state: Shared session context.
        job_post_api: Job API adapter.
        tailoring_api: Tailoring API adapter.

    Returns:
        None.
    """

    @ui.page("/match-review")
    async def match_review_page() -> None:
        """Render matching analysis and selected evidence review."""

        await _load_latest_analysis_if_needed(
            job_state=job_state,
            session_state=session_state,
            job_post_api=job_post_api,
        )

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.label("Match Review").classes("text-2xl font-semibold")
            ui.label(
                "Review evidence selection before snapshot and document generation."
            ).classes("text-sm text-slate-600")

            async def create_plan_action() -> None:
                """Create tailoring plan."""

                await _create_tailoring_plan(
                    profile_state=profile_state,
                    job_state=job_state,
                    session_state=session_state,
                    tailoring_api=tailoring_api,
                )

            async def create_snapshot_action() -> None:
                """Create tailored snapshot."""

                await _create_snapshot(
                    job_state=job_state,
                    session_state=session_state,
                    tailoring_api=tailoring_api,
                )

            with ui.row().classes("gap-3"):
                ui.button("Create Tailoring Plan", on_click=create_plan_action)
                ui.button("Create Snapshot", on_click=create_snapshot_action).props("outline")
                ui.button(
                    "Continue to Output Review",
                    on_click=lambda: ui.navigate.to("/output-review"),
                ).props("outline")

            _render_match_content(job_state=job_state)


async def _load_latest_analysis_if_needed(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    job_post_api: JobPostApi,
) -> None:
    """Load latest analysis when a job is selected but analysis is missing."""

    if job_state.analysis is not None:
        return

    job_post_id = session_state.selected_job_post_id
    if job_post_id is None:
        return

    try:
        job_state.analysis = await run.io_bound(lambda: job_post_api.get_latest_analysis(job_post_id))
    except FrontendApiError:
        return

    analysis_id = job_state.analysis.get("id")
    if isinstance(analysis_id, str):
        session_state.selected_analysis_id = analysis_id


async def _create_tailoring_plan(
    *,
    profile_state: ProfileState,
    job_state: JobState,
    session_state: FrontendSessionState,
    tailoring_api: TailoringApi,
) -> None:
    """Create deterministic tailoring plan for current analysis."""

    analysis_id = session_state.selected_analysis_id
    if analysis_id is None:
        ui.notify("Run job analysis first.", color="warning")
        return

    payload: dict[str, Any] = {
        "job_analysis_id": analysis_id,
        "target_language": session_state.target_language,
        "max_experiences": 4,
        "max_skills": 10,
        "max_educations": 2,
    }
    if profile_state.active_version_id is not None:
        payload["profile_version_id"] = profile_state.active_version_id

    try:
        plan = await run.io_bound(lambda: tailoring_api.create_plan(payload))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    job_state.tailoring_plan = plan
    session_state.selected_plan_id = str(plan.get("id"))
    session_state.selected_snapshot_id = None
    ui.notify("Tailoring plan created.", color="positive")


async def _create_snapshot(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    tailoring_api: TailoringApi,
) -> None:
    """Create tailored snapshot from selected plan."""

    plan_id = session_state.selected_plan_id
    if plan_id is None:
        ui.notify("Create a tailoring plan first.", color="warning")
        return

    try:
        snapshot = await run.io_bound(
            lambda: tailoring_api.create_snapshot(
                {
                    "tailoring_plan_id": plan_id,
                    "rewrites": [],
                    "use_llm_rewrite": False,
                }
            )
        )
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    job_state.snapshot = snapshot
    session_state.selected_snapshot_id = str(snapshot.get("id"))
    ui.notify("Tailored snapshot created.", color="positive")


def _render_match_content(*, job_state: JobState) -> None:
    """Render requirement analysis and selected evidence sections."""

    analysis = job_state.analysis
    if analysis is None:
        ui.label("No analysis loaded. Go to Job Intake to run analysis.").classes(
            "text-sm text-slate-600"
        )
        return

    requirements = [item for item in analysis.get("requirements", []) if isinstance(item, dict)]
    selected_items = _selected_plan_items(job_state.tailoring_plan)

    supported, missing, weak = _split_requirements_by_support(
        requirements=requirements,
        selected_items=selected_items,
    )

    summary_counts = _selected_fact_counts(selected_items)
    render_match_summary(
        matched_skills=summary_counts["skill"],
        matched_experience=summary_counts["experience"],
        matched_academic=0,
        matched_projects=0,
        missing_requirements=len(missing),
    )

    warnings = _build_warnings(missing_count=len(missing), weak_count=len(weak))
    render_warning_panel("Truth and Support Warnings", warnings)

    _render_requirement_sections(
        supported=supported,
        weak=weak,
        missing=missing,
    )
    _render_selected_evidence(selected_items)


def _selected_plan_items(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return selected tailoring plan items."""

    if plan is None:
        return []

    return [
        item
        for item in plan.get("items", [])
        if isinstance(item, dict) and bool(item.get("is_selected"))
    ]


def _split_requirements_by_support(
    *,
    requirements: list[dict[str, Any]],
    selected_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split requirements into supported, missing, and weak categories."""

    supported: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    weak: list[dict[str, Any]] = []

    selected_token_sets = [_tokenize(str(item.get("text", ""))) for item in selected_items]

    for requirement in requirements:
        requirement_tokens = _tokenize(str(requirement.get("text", "")))
        if not requirement_tokens:
            missing.append(requirement)
            continue

        overlap_count = 0
        for token_set in selected_token_sets:
            if requirement_tokens & token_set:
                overlap_count += 1

        if overlap_count == 0:
            missing.append(requirement)
            continue

        if overlap_count == 1 and bool(requirement.get("is_must_have", False)):
            weak.append(requirement)
            continue

        supported.append(requirement)

    return supported, missing, weak


def _selected_fact_counts(selected_items: list[dict[str, Any]]) -> dict[str, int]:
    """Count selected facts by backend fact type."""

    counts = {"skill": 0, "experience": 0, "education": 0, "headline": 0, "summary": 0}
    for item in selected_items:
        fact_type = str(item.get("fact_type", ""))
        if fact_type in counts:
            counts[fact_type] += 1
    return counts


def _build_warnings(*, missing_count: int, weak_count: int) -> list[str]:
    """Build warning list for unsupported and weak requirements."""

    warnings: list[str] = []
    if missing_count > 0:
        warnings.append(
            f"{missing_count} requirement(s) are unsupported by selected evidence."
        )
    if weak_count > 0:
        warnings.append(
            f"{weak_count} requirement(s) have weak support and may risk overstatement."
        )
    if not warnings:
        warnings.append("No critical support gaps detected in current plan.")
    return warnings


def _render_requirement_sections(
    *,
    supported: list[dict[str, Any]],
    weak: list[dict[str, Any]],
    missing: list[dict[str, Any]],
) -> None:
    """Render requirement support sections."""

    with ui.row().classes("w-full gap-3"):
        _render_requirement_list("Supported Requirements", supported, "positive")
        _render_requirement_list("Weakly Supported", weak, "warning")
        _render_requirement_list("Missing Requirements", missing, "negative")


def _render_requirement_list(title: str, requirements: list[dict[str, Any]], color: str) -> None:
    """Render one requirement status list card."""

    with ui.card().classes("w-full"):
        ui.label(title).classes("text-md font-semibold")
        if not requirements:
            ui.label("None").classes("text-sm text-slate-500")
            return

        for requirement in requirements:
            label = str(requirement.get("text", "-"))
            kind = "must-have" if requirement.get("is_must_have") else "nice-to-have"
            ui.badge(kind).props(f"color={color}")
            ui.label(label).classes("text-sm")


def _render_selected_evidence(selected_items: list[dict[str, Any]]) -> None:
    """Render selected evidence entries from tailoring plan."""

    with ui.card().classes("w-full"):
        ui.label("Selected Evidence for Tailoring").classes("text-md font-semibold")
        if not selected_items:
            ui.label("No selected evidence yet. Create a tailoring plan first.").classes(
                "text-sm text-slate-600"
            )
            return

        for item in selected_items:
            fact_type = str(item.get("fact_type", "-"))
            score = int(item.get("relevance_score", 0))
            ui.label(f"[{fact_type}] score={score}: {item.get('text', '-')}").classes("text-sm")


def _tokenize(text: str) -> set[str]:
    """Tokenize text for lightweight requirement-support matching."""

    return {token.lower() for token in _TOKEN_PATTERN.findall(text.lower())}
