"""Match summary component for analysis and evidence review."""

from __future__ import annotations

from nicegui import ui


def render_match_summary(
    *,
    matched_skills: int,
    matched_experience: int,
    matched_academic: int,
    matched_projects: int,
    missing_requirements: int,
) -> None:
    """Render compact match summary metrics.

    Args:
        matched_skills: Count of matched skill facts.
        matched_experience: Count of matched experience facts.
        matched_academic: Count of matched academic achievements.
        matched_projects: Count of matched project facts.
        missing_requirements: Count of missing requirements.

    Returns:
        None.
    """

    with ui.row().classes("w-full gap-3"):
        _metric_card("Matched Skills", matched_skills)
        _metric_card("Matched Experience", matched_experience)
        _metric_card("Matched Academic", matched_academic)
        _metric_card("Matched Projects", matched_projects)
        _metric_card("Missing Requirements", missing_requirements)


def _metric_card(label: str, value: int) -> None:
    """Render one match-summary metric card."""

    with ui.card().classes("min-w-[150px]"):
        ui.label(label).classes("text-xs text-slate-500")
        ui.label(str(value)).classes("text-xl font-semibold")
