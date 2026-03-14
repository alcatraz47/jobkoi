"""Master profile editor page."""

from __future__ import annotations

from typing import Any

from nicegui import run, ui

from app.frontend.components.navigation import render_navigation
from app.frontend.components.profile_forms import render_profile_forms
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.profile_api import ProfileApi
from app.frontend.state.profile_state import ProfileState
from app.frontend.utils.labels import MASTER_PROFILE_BADGE
from app.frontend.utils.mappers import build_profile_request_payload


def register_profile_page(
    *,
    profile_state: ProfileState,
    profile_api: ProfileApi,
) -> None:
    """Register profile editor page route.

    Args:
        profile_state: Shared profile state.
        profile_api: Profile API adapter.

    Returns:
        None.
    """

    @ui.page("/profile")
    async def profile_page() -> None:
        """Render profile editor workflow."""

        await _load_profile_if_exists(profile_state=profile_state, profile_api=profile_api)

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.badge(MASTER_PROFILE_BADGE).props("color=primary")
            ui.label("Master Profile Editor").classes("text-2xl font-semibold")
            ui.label(
                "The master profile is never overwritten by tailoring snapshots."
            ).classes("text-sm text-slate-600")

            versions_container = ui.column().classes("w-full")

            async def save_profile_action() -> None:
                """Persist profile changes."""

                await _save_profile(profile_state=profile_state, profile_api=profile_api)

            async def reload_profile_action() -> None:
                """Reload profile from backend."""

                await _reload_profile(profile_state=profile_state, profile_api=profile_api)

            async def show_versions_action() -> None:
                """Load and render version history."""

                await _show_versions(
                    versions_container=versions_container,
                    profile_api=profile_api,
                )

            with ui.row().classes("gap-3"):
                ui.button("Save Profile", on_click=save_profile_action)
                ui.button("Reload Active Version", on_click=reload_profile_action).props("outline")
                ui.button("Show Version History", on_click=show_versions_action).props("outline")

            render_profile_forms(profile_state)


async def _load_profile_if_exists(*, profile_state: ProfileState, profile_api: ProfileApi) -> None:
    """Load profile into state when it exists."""

    try:
        payload = await run.io_bound(profile_api.get_profile)
    except FrontendApiError as exc:
        if "404" in str(exc):
            return
        ui.notify(str(exc), color="negative")
        return
    profile_state.load_from_profile_response(payload)


async def _reload_profile(*, profile_state: ProfileState, profile_api: ProfileApi) -> None:
    """Reload active profile from backend."""

    await _load_profile_if_exists(profile_state=profile_state, profile_api=profile_api)
    ui.notify("Profile reloaded.", color="info")


async def _save_profile(*, profile_state: ProfileState, profile_api: ProfileApi) -> None:
    """Persist profile as create or versioned update."""

    payload = build_profile_request_payload(profile_state)
    try:
        if profile_state.profile_id is None:
            response = await run.io_bound(lambda: profile_api.create_profile(payload))
        else:
            response = await run.io_bound(lambda: profile_api.update_profile(payload))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    profile_state.load_from_profile_response(response)
    ui.notify("Profile saved with versioning.", color="positive")


async def _show_versions(*, versions_container: Any, profile_api: ProfileApi) -> None:
    """Render profile version history section."""

    versions_container.clear()
    try:
        payload = await run.io_bound(profile_api.list_versions)
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    versions = [item for item in payload.get("versions", []) if isinstance(item, dict)]
    with versions_container:
        with ui.card().classes("w-full"):
            ui.label("Profile Versions").classes("text-md font-semibold")
            if not versions:
                ui.label("No profile versions available yet.").classes("text-sm text-slate-500")
                return

            for item in versions:
                _render_version_row(item)


def _render_version_row(version: dict[str, Any]) -> None:
    """Render one profile version row."""

    with ui.row().classes("w-full items-center justify-between border-b py-2"):
        ui.label(
            f"Version {version.get('version_number', '-')}"
            f" • {version.get('created_at', '-')[:19].replace('T', ' ')}"
        ).classes("text-sm")
        ui.label(
            f"{version.get('full_name', '-')} • {version.get('email', '-')}"
        ).classes("text-xs text-slate-600")
