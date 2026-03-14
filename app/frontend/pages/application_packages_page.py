"""Application package browsing page."""

from __future__ import annotations

from typing import Any

from nicegui import run, ui

from app.frontend.components.navigation import render_navigation
from app.frontend.components.package_list import render_package_list
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.application_package_api import ApplicationPackageApi
from app.frontend.services.document_api import DocumentApi
from app.frontend.state.package_state import PackageState
from app.frontend.state.session_state import FrontendSessionState
from app.frontend.utils.formatting import format_datetime


def register_application_packages_page(
    *,
    package_state: PackageState,
    session_state: FrontendSessionState,
    package_api: ApplicationPackageApi,
    document_api: DocumentApi,
) -> None:
    """Register application packages page route.

    Args:
        package_state: Shared package state.
        session_state: Shared session state.
        package_api: Package API adapter.
        document_api: Document API adapter for download URLs.

    Returns:
        None.
    """

    @ui.page("/application-packages")
    async def application_packages_page() -> None:
        """Render package list and details."""

        await _load_packages(package_state=package_state, package_api=package_api)
        selected_id = _resolve_selected_package_id(session_state=session_state)
        if selected_id:
            await _load_selected_package(
                package_id=selected_id,
                package_state=package_state,
                package_api=package_api,
            )

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.label("Application Packages").classes("text-2xl font-semibold")
            ui.label(
                "Browse reproducible packages with linked snapshot and generated artifacts."
            ).classes("text-sm text-slate-600")

            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("w-1/2"):
                    render_package_list(
                        packages=package_state.packages,
                        on_open=lambda package_id: _open_package(package_id, session_state),
                    )
                with ui.column().classes("w-1/2"):
                    _render_package_details(
                        package=package_state.selected_package,
                        document_api=document_api,
                    )


async def _load_packages(*, package_state: PackageState, package_api: ApplicationPackageApi) -> None:
    """Load all packages into page state."""

    try:
        payload = await run.io_bound(package_api.list_packages)
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    package_state.packages = [
        item
        for item in payload.get("packages", [])
        if isinstance(item, dict)
    ]


def _resolve_selected_package_id(*, session_state: FrontendSessionState) -> str | None:
    """Resolve selected package id from query string or session state."""

    request = ui.context.client.request
    query_id = request.query_params.get("package_id")
    if query_id:
        session_state.selected_package_id = query_id
    return session_state.selected_package_id


async def _load_selected_package(
    *,
    package_id: str,
    package_state: PackageState,
    package_api: ApplicationPackageApi,
) -> None:
    """Load selected package details by identifier."""

    try:
        package_state.selected_package = await run.io_bound(lambda: package_api.get_package(package_id))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")


def _open_package(package_id: str, session_state: FrontendSessionState) -> None:
    """Open one package detail using query-parameter navigation."""

    session_state.selected_package_id = package_id
    ui.navigate.to(f"/application-packages?package_id={package_id}")


def _render_package_details(*, package: dict[str, Any] | None, document_api: DocumentApi) -> None:
    """Render selected package details, documents, and events."""

    with ui.card().classes("w-full"):
        ui.label("Package Details").classes("text-md font-semibold")

        if package is None:
            ui.label("Select a package to view details.").classes("text-sm text-slate-600")
            return

        ui.label(f"ID: {package.get('id', '-')}").classes("text-xs")
        ui.label(
            f"Status: {package.get('status', '-')} • Language: {package.get('language', '-')}"
        ).classes("text-sm")
        ui.label(f"Created: {format_datetime(str(package.get('created_at', '')))}").classes("text-sm")
        ui.label(f"Job Post: {package.get('job_post_id', '-')}").classes("text-sm")

        ui.separator()
        ui.label("Documents").classes("text-sm font-semibold")
        documents = package.get("documents", [])
        if not isinstance(documents, list) or not documents:
            ui.label("No linked documents.").classes("text-sm text-slate-600")
        else:
            for document in documents:
                _render_document_row(document=document, document_api=document_api)

        ui.separator()
        ui.label("Audit Trail").classes("text-sm font-semibold")
        events = package.get("events", [])
        if not isinstance(events, list) or not events:
            ui.label("No audit events.").classes("text-sm text-slate-600")
            return

        for event in events:
            message = str(event.get("message", "-"))
            created_at = format_datetime(str(event.get("created_at", "")))
            ui.label(f"{created_at} • {message}").classes("text-xs")


def _render_document_row(*, document: Any, document_api: DocumentApi) -> None:
    """Render one linked package document row."""

    if not isinstance(document, dict):
        return

    artifact_id = str(document.get("artifact_id", ""))
    file_name = str(document.get("file_name", "-"))
    with ui.row().classes("items-center gap-3"):
        ui.label(file_name).classes("text-sm")
        if artifact_id:
            ui.link("Download", target=document_api.build_download_url(artifact_id), new_tab=True)
