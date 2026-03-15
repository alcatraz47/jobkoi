"""Profile import page for CV and portfolio website ingestion workflows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import run, ui

from app.frontend.components.navigation import render_navigation
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.profile_import_api import ProfileImportApi
from app.frontend.state.import_state import (
    ConflictResolutionDraft,
    ImportDecisionDraft,
    ProfileImportState,
)


def register_profile_import_page(
    *,
    import_state: ProfileImportState,
    profile_import_api: ProfileImportApi,
) -> None:
    """Register profile import workflow page.

    Args:
        import_state: Shared import workflow state.
        profile_import_api: Profile import API adapter.

    Returns:
        None.
    """

    @ui.page("/profile-import")
    async def profile_import_page() -> None:
        """Render profile import workflow page."""

        runs_request_state: dict[str, int] = {"request_id": 0}
        await _load_runs(
            import_state=import_state,
            profile_import_api=profile_import_api,
            runs_request_state=runs_request_state,
        )

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.label("Profile Import").classes("text-2xl font-semibold")
            ui.label(
                "Import CVs or portfolio websites into a review workflow before updating the master profile."
            ).classes("text-sm text-slate-600")

            pending_upload: dict[str, Any] = {"name": "", "bytes": b"", "content_type": "application/octet-stream"}
            website_url = {"value": ""}
            website_max_pages = {"value": 3}
            known_run_statuses = _build_run_status_map(import_state.runs)

            with ui.card().classes("w-full"):
                ui.label("Import Activity").classes("text-md font-semibold")
                ui.label(
                    "Queued and running imports continue in background while you use other pages."
                ).classes("text-sm text-slate-600")
                activity_rows = ui.column().classes("w-full gap-2")
                _render_import_activity_rows(activity_rows=activity_rows, runs=import_state.runs)

            async def poll_import_activity() -> None:
                """Poll run status updates and emit user notifications."""

                await _poll_import_activity(
                    import_state=import_state,
                    profile_import_api=profile_import_api,
                    known_run_statuses=known_run_statuses,
                    runs_request_state=runs_request_state,
                    refresh_run_list=refresh_run_list,
                    activity_rows=activity_rows,
                )

            ui.timer(3.0, poll_import_activity)

            with ui.card().classes("w-full"):
                ui.label("CV Import (PDF/DOCX)").classes("text-md font-semibold")

                async def on_upload(event: Any) -> None:
                    """Capture uploaded file payload."""

                    file_object = getattr(event, "file", None)
                    if file_object is not None and hasattr(file_object, "read"):
                        pending_upload["name"] = str(getattr(file_object, "name", "uploaded_cv") or "uploaded_cv")
                        pending_upload["content_type"] = str(
                            getattr(file_object, "content_type", "application/octet-stream")
                            or "application/octet-stream"
                        )
                        pending_upload["bytes"] = bytes(await file_object.read())
                    else:
                        pending_upload["name"] = str(getattr(event, "name", "uploaded_cv"))
                        pending_upload["content_type"] = str(
                            getattr(event, "type", "application/octet-stream")
                            or "application/octet-stream"
                        )
                        pending_upload["bytes"] = _read_upload_bytes_legacy(getattr(event, "content", None))

                    if pending_upload["bytes"]:
                        ui.notify(f"Loaded file: {pending_upload['name']}", color="info")
                    else:
                        ui.notify("Could not read uploaded file bytes.", color="negative")

                def on_upload_rejected(_: Any) -> None:
                    """Notify when browser upload constraints reject a file."""

                    ui.notify(
                        "Upload rejected. Use PDF/DOCX and keep size under 20 MB.",
                        color="negative",
                    )

                ui.upload(
                    on_upload=on_upload,
                    on_rejected=on_upload_rejected,
                    auto_upload=True,
                ).props("accept=.pdf,.docx max-file-size=20971520")

                with ui.dialog().props("persistent") as cv_import_progress, ui.card().classes("items-center gap-3 p-6"):
                    ui.spinner(size="lg")
                    ui.label("Reading CV and extracting structured profile data. Please wait...").classes("text-sm")

                async def import_cv_action() -> None:
                    """Submit CV import request."""

                    if not pending_upload["bytes"]:
                        ui.notify("Upload a PDF or DOCX file first.", color="warning")
                        return

                    cv_import_progress.open()
                    ui.notify("Queueing CV import. You can continue using the app.", color="info")
                    try:
                        run_payload = await run.io_bound(
                            lambda: profile_import_api.import_cv(
                                file_name=str(pending_upload["name"] or "uploaded_cv"),
                                file_bytes=bytes(pending_upload["bytes"]),
                                content_type=str(pending_upload["content_type"]),
                            )
                        )
                    except FrontendApiError as exc:
                        ui.notify(str(exc), color="negative")
                        return
                    finally:
                        cv_import_progress.close()

                    import_state.load_selected_run(run_payload)
                    await _load_runs(
                        import_state=import_state,
                        profile_import_api=profile_import_api,
                        runs_request_state=runs_request_state,
                    )
                    _render_import_activity_rows(activity_rows=activity_rows, runs=import_state.runs)
                    refresh_run_list()
                    ui.notify("CV import queued. You will be notified when parsing finishes.", color="positive")

                ui.button("Start CV Import", on_click=import_cv_action)

            with ui.card().classes("w-full"):
                ui.label("Portfolio Website Import").classes("text-md font-semibold")
                url_input = ui.input(
                    "Public URL",
                    value=website_url["value"],
                ).classes("w-full max-w-2xl")
                url_input.bind_value(website_url, "value")

                max_pages_input = ui.number(
                    "Max pages",
                    value=website_max_pages["value"],
                    min=1,
                    max=10,
                    step=1,
                ).classes("w-56")
                max_pages_input.bind_value(website_max_pages, "value")
                ui.label("Same-domain crawl limit (1-10 pages). ").classes("text-xs text-slate-500")

                with ui.dialog().props("persistent") as website_import_progress, ui.card().classes("items-center gap-3 p-6"):
                    ui.spinner(size="lg")
                    ui.label("Fetching and parsing website data. Please wait...").classes("text-sm")

                async def import_website_action() -> None:
                    """Submit website import request."""

                    url_value = website_url["value"].strip()
                    if not url_value:
                        ui.notify("Enter a portfolio URL first.", color="warning")
                        return

                    website_import_progress.open()
                    ui.notify("Queueing website import. You can continue using the app.", color="info")
                    try:
                        run_payload = await run.io_bound(
                            lambda: profile_import_api.import_website(
                                {
                                    "url": url_value,
                                    "max_pages": int(website_max_pages["value"]),
                                }
                            )
                        )
                    except FrontendApiError as exc:
                        ui.notify(str(exc), color="negative")
                        return
                    finally:
                        website_import_progress.close()

                    import_state.load_selected_run(run_payload)
                    await _load_runs(
                        import_state=import_state,
                        profile_import_api=profile_import_api,
                        runs_request_state=runs_request_state,
                    )
                    _render_import_activity_rows(activity_rows=activity_rows, runs=import_state.runs)
                    refresh_run_list()
                    ui.notify("Website import queued. You will be notified when parsing finishes.", color="positive")

                ui.button("Start Website Import", on_click=import_website_action)

            run_list_container = ui.column().classes("w-full")

            def refresh_run_list() -> None:
                """Refresh import run list card contents."""

                run_list_container.clear()
                with run_list_container:
                    _render_run_list(
                        import_state=import_state,
                        profile_import_api=profile_import_api,
                        runs_request_state=runs_request_state,
                        refresh_run_list=refresh_run_list,
                    )

            refresh_run_list()

            _render_selected_run_review(
                import_state=import_state,
                profile_import_api=profile_import_api,
                runs_request_state=runs_request_state,
            )


def _render_run_list(
    *,
    import_state: ProfileImportState,
    profile_import_api: ProfileImportApi,
    runs_request_state: dict[str, int],
    refresh_run_list: Callable[[], None],
) -> None:
    """Render import run list panel with retract and delete actions."""

    with ui.card().classes("w-full"):
        ui.label("Import Runs").classes("text-md font-semibold")
        if not import_state.runs:
            ui.label("No import runs yet.").classes("text-sm text-slate-600")
            return

        for item in import_state.runs:
            run_id = str(item.get("id", ""))
            if not run_id:
                continue

            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            label = str(source.get("source_label", "-"))
            status = str(item.get("status", "-"))
            created_at = str(item.get("created_at", ""))

            async def retract_action(target_run_id: str = run_id) -> None:
                """Mark one run as rejected (retracted) from list view."""

                try:
                    run_payload = await run.io_bound(
                        lambda: profile_import_api.reject_run(target_run_id, "Retracted from import run list.")
                    )
                except FrontendApiError as exc:
                    ui.notify(str(exc), color="negative")
                    return

                import_state.load_selected_run(run_payload)
                await _load_runs(
                    import_state=import_state,
                    profile_import_api=profile_import_api,
                    runs_request_state=runs_request_state,
                )
                refresh_run_list()
                ui.notify("Import run retracted.", color="warning")
                ui.navigate.to(f"/profile-import?run_id={target_run_id}")

            async def delete_action(target_run_id: str = run_id) -> None:
                """Delete one import run from backend and list view."""

                try:
                    await run.io_bound(lambda: profile_import_api.delete_run(target_run_id))
                except FrontendApiError as exc:
                    ui.notify(str(exc), color="negative")
                    return

                if import_state.selected_run and str(import_state.selected_run.get("id")) == target_run_id:
                    import_state.selected_run = None
                    import_state.field_decisions = {}
                    import_state.conflict_resolutions = {}

                await _load_runs(
                    import_state=import_state,
                    profile_import_api=profile_import_api,
                    runs_request_state=runs_request_state,
                )
                refresh_run_list()
                ui.notify("Import run deleted.", color="warning")
                ui.navigate.to("/profile-import")

            with ui.row().classes("w-full items-center justify-between border-b py-2"):
                ui.label(f"{label} • {status} • {created_at[:19].replace('T', ' ')}").classes("text-sm")
                with ui.row().classes("items-center gap-2"):
                    ui.link("Open", target=f"/profile-import?run_id={run_id}")
                    if status not in {"rejected"}:
                        ui.button("Retract", on_click=retract_action).props("flat color=warning")
                    ui.button("Delete", on_click=delete_action).props("flat color=negative")


def _render_selected_run_review(
    *,
    import_state: ProfileImportState,
    profile_import_api: ProfileImportApi,
    runs_request_state: dict[str, int],
) -> None:
    """Render selected run review form and apply actions."""

    run_id = ui.context.client.request.query_params.get("run_id")
    if run_id:
        current = next((item for item in import_state.runs if str(item.get("id")) == run_id), None)
        if current is not None:
            import_state.load_selected_run(current)

    selected = import_state.selected_run
    if selected is None:
        return

    with ui.card().classes("w-full"):
        ui.label("Import Review").classes("text-md font-semibold")
        ui.label(f"Run ID: {selected.get('id', '-')}").classes("text-xs")
        ui.label(f"Status: {selected.get('status', '-')}").classes("text-sm")

        ui.separator()
        ui.label("Field Decisions").classes("text-sm font-semibold")

        fields = [item for item in selected.get("fields", []) if isinstance(item, dict)]
        if not fields:
            ui.label("No extracted fields found.").classes("text-sm text-slate-600")
        else:
            for field in fields:
                _render_field_decision_row(import_state=import_state, field=field)

        ui.separator()
        ui.label("Conflict Resolutions").classes("text-sm font-semibold")

        conflicts = [item for item in selected.get("conflicts", []) if isinstance(item, dict)]
        if not conflicts:
            ui.label("No conflicts detected.").classes("text-sm text-slate-600")
        else:
            with ui.row().classes("gap-2 pb-2"):
                ui.button(
                    "Resolve All: Keep Existing",
                    on_click=lambda: _set_all_conflict_resolutions(
                        import_state=import_state,
                        conflicts=conflicts,
                        resolution_status="keep_existing",
                    ),
                ).props("outline size=sm")
                ui.button(
                    "Resolve All: Accept Imported",
                    on_click=lambda: _set_all_conflict_resolutions(
                        import_state=import_state,
                        conflicts=conflicts,
                        resolution_status="accept_import",
                    ),
                ).props("outline size=sm")

            for conflict in conflicts:
                _render_conflict_resolution_row(import_state=import_state, conflict=conflict)

        async def save_review_action() -> None:
            """Submit decision and resolution updates."""

            if import_state.selected_run is None:
                return
            selected_id = str(import_state.selected_run.get("id", ""))
            if not selected_id:
                return

            payload = _build_review_payload(import_state)

            try:
                run_payload = await run.io_bound(
                    lambda: profile_import_api.review_run(selected_id, payload)
                )
            except FrontendApiError as exc:
                ui.notify(str(exc), color="negative")
                return

            import_state.load_selected_run(run_payload)
            await _load_runs(
                import_state=import_state,
                profile_import_api=profile_import_api,
                runs_request_state=runs_request_state,
            )
            ui.notify("Review decisions saved.", color="positive")
            ui.navigate.to(f"/profile-import?run_id={selected_id}")

        async def apply_action() -> None:
            """Apply reviewed import run to master profile."""

            if import_state.selected_run is None:
                return
            selected_id = str(import_state.selected_run.get("id", ""))
            if not selected_id:
                return

            review_payload = _build_review_payload(import_state)
            try:
                reviewed_run = await run.io_bound(
                    lambda: profile_import_api.review_run(selected_id, review_payload)
                )
            except FrontendApiError as exc:
                ui.notify(str(exc), color="negative")
                return

            import_state.load_selected_run(reviewed_run)

            try:
                response = await run.io_bound(lambda: profile_import_api.apply_run(selected_id))
            except FrontendApiError as exc:
                pending_count = _count_pending_conflicts(import_state.selected_run)
                if pending_count > 0:
                    ui.notify(
                        (
                            f"Resolve {pending_count} pending conflict(s) first. "
                            "Choose Keep Existing or Accept Imported, then Apply."
                        ),
                        color="warning",
                    )
                    return

                ui.notify(str(exc), color="negative")
                return

            run_payload = response.get("run", {})
            if isinstance(run_payload, dict):
                import_state.load_selected_run(run_payload)
            await _load_runs(
                import_state=import_state,
                profile_import_api=profile_import_api,
                runs_request_state=runs_request_state,
            )
            ui.notify("Imported data applied as new profile version.", color="positive")
            ui.navigate.to("/profile")

        async def reject_action() -> None:
            """Reject selected import run."""

            if import_state.selected_run is None:
                return
            selected_id = str(import_state.selected_run.get("id", ""))
            if not selected_id:
                return

            try:
                run_payload = await run.io_bound(lambda: profile_import_api.reject_run(selected_id, None))
            except FrontendApiError as exc:
                ui.notify(str(exc), color="negative")
                return

            import_state.load_selected_run(run_payload)
            await _load_runs(
                import_state=import_state,
                profile_import_api=profile_import_api,
                runs_request_state=runs_request_state,
            )
            ui.notify("Import run rejected.", color="warning")
            ui.navigate.to(f"/profile-import?run_id={selected_id}")

        with ui.row().classes("gap-3"):
            ui.button("Save Review Decisions", on_click=save_review_action)
            ui.button("Apply to Master Profile", on_click=apply_action).props("outline")
            ui.button("Reject Import", on_click=reject_action).props("outline color=negative")


def _render_field_decision_row(*, import_state: ProfileImportState, field: dict[str, Any]) -> None:
    """Render editable field-decision row."""

    field_id = str(field.get("id", ""))
    if not field_id:
        return

    decision = import_state.field_decisions.setdefault(field_id, ImportDecisionDraft())
    extracted_value = str(field.get("extracted_value") or "")
    confidence_score = int(field.get("confidence_score") or 0)
    review_risk = str(field.get("review_risk") or "unknown")
    recommended = str(field.get("recommended_decision") or "review")

    with ui.card().classes("w-full bg-slate-50"):
        ui.label(str(field.get("field_path", "-"))).classes("text-sm font-semibold")
        ui.label(extracted_value or "(empty)").classes("text-xs text-slate-700 whitespace-pre-wrap break-words")
        ui.label(
            f"Confidence: {confidence_score} | Risk: {review_risk} | Recommended: {recommended}"
        ).classes("text-xs text-slate-500")

        ui.select(
            options={"approve": "Approve", "edit": "Edit", "reject": "Reject"},
            value=decision.decision,
            label="Decision",
            on_change=lambda event, fid=field_id: _set_field_decision(
                import_state,
                fid,
                str(event.value),
            ),
        ).classes("w-full").props("outlined")

        ui.input(
            "Edited value",
            value=decision.edited_value or extracted_value,
            on_change=lambda event, fid=field_id: _set_field_edited_value(
                import_state,
                fid,
                str(event.value),
            ),
        ).classes("w-full").props("outlined")
        ui.input(
            "Reviewer note",
            value=decision.reviewer_note or "",
            on_change=lambda event, fid=field_id: _set_field_note(
                import_state,
                fid,
                str(event.value),
            ),
        ).classes("w-full").props("outlined")


def _render_conflict_resolution_row(*, import_state: ProfileImportState, conflict: dict[str, Any]) -> None:
    """Render editable conflict-resolution row."""

    conflict_id = str(conflict.get("id", ""))
    if not conflict_id:
        return

    resolution = import_state.conflict_resolutions.setdefault(
        conflict_id,
        ConflictResolutionDraft(),
    )

    with ui.card().classes("w-full bg-amber-50"):
        ui.label(str(conflict.get("field_path", "-"))).classes("text-sm font-semibold text-amber-900")
        ui.label(
            f"Existing: {conflict.get('existing_value', '-')}",
        ).classes("text-xs text-amber-900 whitespace-pre-wrap break-words")
        ui.label(
            f"Imported: {conflict.get('imported_value', '-')}",
        ).classes("text-xs text-amber-900 whitespace-pre-wrap break-words")

        ui.select(
            options={
                "pending": "Pending",
                "keep_existing": "Keep Existing",
                "accept_import": "Accept Imported",
                "manual": "Manual",
                "rejected": "Reject Imported",
            },
            value=resolution.resolution_status,
            label="Resolution",
            on_change=lambda event, cid=conflict_id: _set_conflict_resolution_status(
                import_state,
                cid,
                str(event.value),
            ),
        ).classes("w-full").props("outlined")
        ui.input(
            "Resolution note",
            value=resolution.resolution_note or "",
            on_change=lambda event, cid=conflict_id: _set_conflict_resolution_note(
                import_state,
                cid,
                str(event.value),
            ),
        ).classes("w-full").props("outlined")


def _build_review_payload(import_state: ProfileImportState) -> dict[str, list[dict[str, Any]]]:
    """Build review payload from current import-state drafts.

    Args:
        import_state: Mutable import review state.

    Returns:
        Serialized review payload.
    """

    return {
        "decisions": [
            {
                "field_id": field_id,
                "decision": decision.decision,
                "edited_value": decision.edited_value,
                "reviewer_note": decision.reviewer_note,
            }
            for field_id, decision in import_state.field_decisions.items()
        ],
        "conflict_resolutions": [
            {
                "conflict_id": conflict_id,
                "resolution_status": resolution.resolution_status,
                "resolution_note": resolution.resolution_note,
            }
            for conflict_id, resolution in import_state.conflict_resolutions.items()
        ],
    }


def _set_all_conflict_resolutions(
    *,
    import_state: ProfileImportState,
    conflicts: list[dict[str, Any]],
    resolution_status: str,
) -> None:
    """Set one resolution status for all visible conflict rows.

    Args:
        import_state: Mutable import review state.
        conflicts: Conflict row payloads.
        resolution_status: Resolution status to assign.

    Returns:
        None.
    """

    count = 0
    for conflict in conflicts:
        conflict_id = str(conflict.get("id", ""))
        if not conflict_id:
            continue

        draft = import_state.conflict_resolutions.setdefault(conflict_id, ConflictResolutionDraft())
        draft.resolution_status = resolution_status
        count += 1

    if count > 0:
        ui.notify(
            f"Set {count} conflict(s) to {resolution_status}. Click Save or Apply.",
            color="info",
        )


def _count_pending_conflicts(run_payload: dict[str, Any] | None) -> int:
    """Count conflicts still marked as pending.

    Args:
        run_payload: Selected run payload.

    Returns:
        Number of pending conflict rows.
    """

    if not isinstance(run_payload, dict):
        return 0

    count = 0
    for conflict in run_payload.get("conflicts", []):
        if not isinstance(conflict, dict):
            continue
        if str(conflict.get("resolution_status", "pending")) == "pending":
            count += 1
    return count


def _build_run_status_map(runs: list[dict[str, Any]]) -> dict[str, str]:
    """Build identifier-to-status mapping from run payloads.

    Args:
        runs: Import run payload list.

    Returns:
        Mapping of run identifiers to statuses.
    """

    mapping: dict[str, str] = {}
    for item in runs:
        run_id = str(item.get("id", ""))
        if not run_id:
            continue
        mapping[run_id] = str(item.get("status", ""))
    return mapping


def _render_import_activity_rows(*, activity_rows: Any, runs: list[dict[str, Any]]) -> None:
    """Render compact import activity rows for queued/running runs.

    Args:
        activity_rows: NiceGUI container for rows.
        runs: Import run payload list.
    """

    activity_rows.clear()
    active = [item for item in runs if str(item.get("status", "")).lower() in {"queued", "running"}]
    if not active:
        with activity_rows:
            ui.label("No background import jobs running.").classes("text-sm text-slate-600")
        return

    with activity_rows:
        for item in active:
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            label = str(source.get("source_label", "-"))
            status = str(item.get("status", "-")).upper()
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(label).classes("text-sm")
                ui.badge(status).props("color=info")


async def _poll_import_activity(
    *,
    import_state: ProfileImportState,
    profile_import_api: ProfileImportApi,
    known_run_statuses: dict[str, str],
    runs_request_state: dict[str, int],
    refresh_run_list: Callable[[], None],
    activity_rows: Any,
) -> None:
    """Poll import runs, refresh activity panel, and notify on status transitions.

    Args:
        import_state: Shared import workflow state.
        profile_import_api: Profile import API adapter.
        known_run_statuses: Mutable map of known statuses by run id.
        runs_request_state: Request version state for race-safe run refreshes.
        refresh_run_list: Callback to refresh rendered run list contents.
        activity_rows: NiceGUI container for activity rows.
    """

    previous_statuses = dict(known_run_statuses)
    await _load_runs(
        import_state=import_state,
        profile_import_api=profile_import_api,
        runs_request_state=runs_request_state,
    )
    _render_import_activity_rows(activity_rows=activity_rows, runs=import_state.runs)
    refresh_run_list()

    latest_statuses = _build_run_status_map(import_state.runs)
    known_run_statuses.clear()
    known_run_statuses.update(latest_statuses)

    for item in import_state.runs:
        run_id = str(item.get("id", ""))
        if not run_id:
            continue

        current_status = latest_statuses.get(run_id, "")
        previous_status = previous_statuses.get(run_id)
        if previous_status is None or current_status == previous_status:
            continue

        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        source_label = str(source.get("source_label", "Import run"))

        if current_status == "running":
            ui.notify(f"Import started: {source_label}", color="info")
        elif current_status == "extracted":
            ui.notify(f"Import completed: {source_label}", color="positive")
        elif current_status == "failed":
            ui.notify(f"Import failed: {source_label}", color="negative")

    selected_run_id = ""
    if isinstance(import_state.selected_run, dict):
        selected_run_id = str(import_state.selected_run.get("id", ""))

    if not selected_run_id:
        return

    selected_status = latest_statuses.get(selected_run_id)
    if selected_status not in {"extracted", "reviewed", "applied", "failed"}:
        return

    if previous_statuses.get(selected_run_id) == selected_status:
        return

    try:
        refreshed = await run.io_bound(lambda: profile_import_api.get_run(selected_run_id))
    except FrontendApiError:
        return

    import_state.load_selected_run(refreshed)



async def _load_runs(
    *,
    import_state: ProfileImportState,
    profile_import_api: ProfileImportApi,
    runs_request_state: dict[str, int],
) -> None:
    """Load import runs into page state."""

    request_id = int(runs_request_state.get("request_id", 0)) + 1
    runs_request_state["request_id"] = request_id

    try:
        payload = await run.io_bound(profile_import_api.list_runs)
    except FrontendApiError as exc:
        if request_id == int(runs_request_state.get("request_id", 0)):
            ui.notify(str(exc), color="negative")
        return

    if request_id != int(runs_request_state.get("request_id", 0)):
        return

    import_state.runs = [item for item in payload.get("runs", []) if isinstance(item, dict)]


def _set_field_decision(import_state: ProfileImportState, field_id: str, decision: str) -> None:
    """Set field decision value in import state."""

    draft = import_state.field_decisions.setdefault(field_id, ImportDecisionDraft())
    draft.decision = decision


def _set_field_edited_value(import_state: ProfileImportState, field_id: str, edited_value: str) -> None:
    """Set edited value in import state."""

    draft = import_state.field_decisions.setdefault(field_id, ImportDecisionDraft())
    draft.edited_value = edited_value


def _set_field_note(import_state: ProfileImportState, field_id: str, note: str) -> None:
    """Set reviewer note in import state."""

    draft = import_state.field_decisions.setdefault(field_id, ImportDecisionDraft())
    draft.reviewer_note = note or None


def _set_conflict_resolution_status(
    import_state: ProfileImportState,
    conflict_id: str,
    status: str,
) -> None:
    """Set conflict resolution status in import state."""

    draft = import_state.conflict_resolutions.setdefault(conflict_id, ConflictResolutionDraft())
    draft.resolution_status = status


def _set_conflict_resolution_note(
    import_state: ProfileImportState,
    conflict_id: str,
    note: str,
) -> None:
    """Set conflict resolution note in import state."""

    draft = import_state.conflict_resolutions.setdefault(conflict_id, ConflictResolutionDraft())
    draft.resolution_note = note or None



def _read_upload_bytes_legacy(content: Any) -> bytes:
    """Read upload bytes for legacy NiceGUI upload events.

    Args:
        content: Legacy upload content object.

    Returns:
        Raw uploaded bytes, or empty bytes when content cannot be read.
    """

    if content is None:
        return b""

    if isinstance(content, (bytes, bytearray)):
        return bytes(content)

    if hasattr(content, "read"):
        try:
            raw = content.read()
        except Exception:
            raw = None
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str):
            return raw.encode("utf-8", errors="ignore")

    file_object = getattr(content, "file", None)
    if hasattr(file_object, "read"):
        try:
            raw = file_object.read()
        except Exception:
            raw = None
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str):
            return raw.encode("utf-8", errors="ignore")

    return b""
