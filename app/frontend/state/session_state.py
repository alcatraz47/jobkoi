"""Session-level frontend state containers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrontendSessionState:
    """Global session state for current frontend workflow context."""

    selected_job_post_id: str | None = None
    selected_analysis_id: str | None = None
    selected_plan_id: str | None = None
    selected_snapshot_id: str | None = None
    selected_package_id: str | None = None
    target_language: str = "en"
