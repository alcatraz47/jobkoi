"""Dashboard page for Jobkoi frontend workflow."""

from __future__ import annotations

from typing import Any

from nicegui import run, ui

from app.frontend.components.navigation import render_navigation
from app.frontend.components.package_list import render_package_list
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.application_package_api import ApplicationPackageApi
from app.frontend.services.profile_api import ProfileApi
from app.frontend.state.package_state import PackageState
from app.frontend.state.profile_state import ProfileState
from app.frontend.utils.formatting import format_datetime


def register_dashboard_page(
    *,
    profile_state: ProfileState,
    package_state: PackageState,
    profile_api: ProfileApi,
    package_api: ApplicationPackageApi,
) -> None:
    """Register dashboard route.

    Args:
        profile_state: Shared profile state.
        package_state: Shared package state.
        profile_api: Profile API adapter.
        package_api: Application package API adapter.

    Returns:
        None.
    """

    @ui.page("/")
    async def dashboard_page() -> None:
        """Render dashboard page."""

        await _load_dashboard_state(
            profile_state=profile_state,
            package_state=package_state,
            profile_api=profile_api,
            package_api=package_api,
        )

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            _render_repository_scope_warning()
            ui.label("Dashboard").classes("text-2xl font-semibold")
            ui.label(
                "Truth-constrained tailoring workflow: profile, intake, analysis, review, and export."
            ).classes("text-sm text-slate-600")

            with ui.row().classes("w-full gap-3"):
                ui.button("Edit Master Profile", on_click=lambda: ui.navigate.to("/profile"))
                ui.button("Start Job Intake", on_click=lambda: ui.navigate.to("/job-intake"))

            _render_profile_completeness(profile_state)
            _render_recent_packages(package_state)
            _render_recent_documents(package_state.packages)


def _render_repository_scope_warning() -> None:
    """Render top-level project scope and caution warning."""

    with ui.card().classes("w-full border-l-4 border-amber-500 bg-amber-50"):
        ui.label("Warning").classes("text-md font-semibold text-amber-900")
        ui.label(
            "This repository is developed using vibe coding and is intended for personal use."
        ).classes("text-sm text-amber-900")
        ui.label(
            "It is not developed with a multi-user focus. Review and harden it before broader use."
        ).classes("text-sm text-amber-900")


async def _load_dashboard_state(
    *,
    profile_state: ProfileState,
    package_state: PackageState,
    profile_api: ProfileApi,
    package_api: ApplicationPackageApi,
) -> None:
    """Load profile and package data for dashboard cards."""

    await _load_profile(profile_state=profile_state, profile_api=profile_api)
    await _load_packages(package_state=package_state, package_api=package_api)


async def _load_profile(*, profile_state: ProfileState, profile_api: ProfileApi) -> None:
    """Load active profile into frontend state."""

    try:
        payload = await run.io_bound(profile_api.get_profile)
    except FrontendApiError as exc:
        if "404" not in str(exc):
            ui.notify(str(exc), color="negative")
        return
    profile_state.load_from_profile_response(payload)


async def _load_packages(*, package_state: PackageState, package_api: ApplicationPackageApi) -> None:
    """Load package list into state container."""

    try:
        payload = await run.io_bound(package_api.list_packages)
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    package_state.packages = [item for item in payload.get("packages", []) if isinstance(item, dict)]


def _render_profile_completeness(profile_state: ProfileState) -> None:
    """Render profile completeness summary card."""

    summary = profile_state.completeness_summary()
    with ui.card().classes("w-full"):
        ui.label("Profile Completeness").classes("text-md font-semibold")
        with ui.row().classes("w-full gap-3"):
            for label, value in (
                ("Experience", summary["experiences"]),
                ("Skills", summary["skills"]),
                ("Education", summary["educations"]),
                ("Academic", summary["academic_achievements"]),
                ("Projects", summary["projects"]),
                ("Certifications", summary["certifications"]),
                ("Languages", summary["languages"]),
            ):
                with ui.card().classes("min-w-[110px]"):
                    ui.label(label).classes("text-xs text-slate-500")
                    ui.label(str(value)).classes("text-lg font-semibold")


def _render_recent_packages(package_state: PackageState) -> None:
    """Render recent package list section."""

    with ui.card().classes("w-full"):
        ui.label("Recent Application Packages").classes("text-md font-semibold")
        recent = package_state.recent_packages(limit=5)
        render_package_list(
            packages=recent,
            on_open=lambda package_id: ui.navigate.to(f"/application-packages?package_id={package_id}"),
        )


def _render_recent_documents(packages: list[dict[str, Any]]) -> None:
    """Render recent generated documents from package links."""

    documents = _collect_recent_documents(packages)
    with ui.card().classes("w-full"):
        ui.label("Recent Generated Documents").classes("text-md font-semibold")
        if not documents:
            ui.label("No generated documents linked yet.").classes("text-sm text-slate-600")
            return

        for item in documents:
            ui.label(
                f"{item['file_name']} • {item['document_type']} • {format_datetime(item['created_at'])}"
            ).classes("text-sm")


def _collect_recent_documents(packages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Collect up to 8 recent documents from package payloads."""

    collected: list[dict[str, str]] = []
    for package in packages:
        for document in package.get("documents", []):
            if not isinstance(document, dict):
                continue
            collected.append(
                {
                    "file_name": str(document.get("file_name", "-")),
                    "document_type": str(document.get("document_type", "-")),
                    "created_at": str(document.get("created_at", "")),
                }
            )
    return collected[:8]
