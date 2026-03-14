"""Output review page for generated CV and cover-letter artifacts."""

from __future__ import annotations

from typing import Any

from nicegui import run, ui

from app.frontend.components.cover_letter_preview import render_cover_letter_preview
from app.frontend.components.cv_preview import render_cv_preview
from app.frontend.components.navigation import render_navigation
from app.frontend.components.warning_panel import render_warning_panel
from app.frontend.services.api_client import FrontendApiError
from app.frontend.services.application_package_api import ApplicationPackageApi
from app.frontend.services.document_api import DocumentApi
from app.frontend.services.tailoring_api import TailoringApi
from app.frontend.state.job_state import JobState
from app.frontend.state.package_state import ClaimValidationResult, PackageState
from app.frontend.state.session_state import FrontendSessionState
from app.frontend.utils.labels import SNAPSHOT_PROFILE_BADGE


def register_output_review_page(
    *,
    job_state: JobState,
    package_state: PackageState,
    session_state: FrontendSessionState,
    tailoring_api: TailoringApi,
    document_api: DocumentApi,
    package_api: ApplicationPackageApi,
) -> None:
    """Register output review page route.

    Args:
        job_state: Shared job workflow state.
        package_state: Shared package state.
        session_state: Shared session selection state.
        tailoring_api: Tailoring API adapter.
        document_api: Document API adapter.
        package_api: Application package adapter.

    Returns:
        None.
    """

    @ui.page("/output-review")
    async def output_review_page() -> None:
        """Render output review workflow page."""

        await _load_snapshot_if_needed(
            job_state=job_state,
            session_state=session_state,
            tailoring_api=tailoring_api,
        )
        await _load_existing_documents_if_needed(job_state=job_state, document_api=document_api)
        _refresh_claim_validation(job_state=job_state, package_state=package_state)

        render_navigation()
        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            ui.badge(SNAPSHOT_PROFILE_BADGE).props("color=secondary")
            ui.label("Output Review").classes("text-2xl font-semibold")
            ui.label(
                "Review generated outputs and warnings before export and manual submission."
            ).classes("text-sm text-slate-600")

            async def generate_cv_action() -> None:
                """Generate CV artifacts."""

                await _generate_document(
                    document_type="cv",
                    job_state=job_state,
                    session_state=session_state,
                    document_api=document_api,
                )

            async def generate_cover_action() -> None:
                """Generate cover-letter artifacts."""

                await _generate_document(
                    document_type="cover_letter",
                    job_state=job_state,
                    session_state=session_state,
                    document_api=document_api,
                )

            async def create_package_action() -> None:
                """Create application package."""

                await _create_application_package(
                    job_state=job_state,
                    package_state=package_state,
                    session_state=session_state,
                    package_api=package_api,
                )

            with ui.row().classes("gap-3"):
                ui.button("Generate CV", on_click=generate_cv_action)
                ui.button("Generate Cover Letter", on_click=generate_cover_action).props("outline")
                ui.button("Create Application Package", on_click=create_package_action).props("outline")
                ui.button(
                    "Open Packages",
                    on_click=lambda: ui.navigate.to("/application-packages"),
                ).props("outline")

            warnings = _build_output_warnings(job_state=job_state)
            render_warning_panel("Output Warnings", warnings)

            _render_claim_validation_results(package_state.claim_validation)
            await _render_document_previews(job_state=job_state, document_api=document_api)
            _render_export_links(job_state=job_state, document_api=document_api)


async def _load_snapshot_if_needed(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
    tailoring_api: TailoringApi,
) -> None:
    """Load selected snapshot when id is present and state is empty."""

    if job_state.snapshot is not None:
        return

    snapshot_id = session_state.selected_snapshot_id
    if snapshot_id is None:
        return

    try:
        job_state.snapshot = await run.io_bound(lambda: tailoring_api.get_snapshot(snapshot_id))
    except FrontendApiError:
        return


async def _load_existing_documents_if_needed(*, job_state: JobState, document_api: DocumentApi) -> None:
    """Load previously generated artifacts for current snapshot."""

    snapshot = job_state.snapshot
    if snapshot is None:
        return

    if job_state.generated_documents:
        return

    snapshot_id = str(snapshot.get("id", ""))
    if not snapshot_id:
        return

    try:
        response = await run.io_bound(lambda: document_api.list_snapshot_documents(snapshot_id))
    except FrontendApiError:
        return

    grouped = _group_artifacts_by_type(response.get("artifacts", []))
    job_state.generated_documents = grouped


async def _generate_document(
    *,
    document_type: str,
    job_state: JobState,
    session_state: FrontendSessionState,
    document_api: DocumentApi,
) -> None:
    """Generate one document type for selected snapshot."""

    snapshot_id = session_state.selected_snapshot_id
    if snapshot_id is None:
        ui.notify("Create a tailored snapshot first.", color="warning")
        return

    payload = {
        "snapshot_id": snapshot_id,
        "language": session_state.target_language,
        "formats": ["html", "pdf", "docx"],
    }

    try:
        if document_type == "cv":
            response = await run.io_bound(lambda: document_api.generate_cv(payload))
        else:
            response = await run.io_bound(lambda: document_api.generate_cover_letter(payload))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    artifacts = [item for item in response.get("artifacts", []) if isinstance(item, dict)]
    if not artifacts:
        ui.notify("No artifacts were generated.", color="warning")
        return

    key = "cv" if document_type == "cv" else "cover_letter"
    job_state.generated_documents[key] = artifacts
    ui.notify(f"Generated {key} artifacts.", color="positive")


async def _create_application_package(
    *,
    job_state: JobState,
    package_state: PackageState,
    session_state: FrontendSessionState,
    package_api: ApplicationPackageApi,
) -> None:
    """Create reproducible package linked to current workflow entities."""

    payload = _build_package_payload(job_state=job_state, session_state=session_state)
    if payload is None:
        ui.notify("Missing workflow dependencies for package creation.", color="warning")
        return

    try:
        package = await run.io_bound(lambda: package_api.create_package(payload))
    except FrontendApiError as exc:
        ui.notify(str(exc), color="negative")
        return

    package_state.selected_package = package
    package_state.packages.insert(0, package)
    session_state.selected_package_id = str(package.get("id"))
    ui.notify("Application package created.", color="positive")


def _build_package_payload(
    *,
    job_state: JobState,
    session_state: FrontendSessionState,
) -> dict[str, Any] | None:
    """Build package payload from selected workflow entities."""

    job_post_id = session_state.selected_job_post_id
    analysis_id = session_state.selected_analysis_id
    plan_id = session_state.selected_plan_id
    snapshot_id = session_state.selected_snapshot_id
    if not all([job_post_id, analysis_id, plan_id, snapshot_id]):
        return None

    artifact_ids: list[str] = []
    for artifacts in job_state.generated_documents.values():
        artifact_ids.extend(str(item.get("id")) for item in artifacts if item.get("id"))

    return {
        "job_post_id": job_post_id,
        "job_analysis_id": analysis_id,
        "tailoring_plan_id": plan_id,
        "profile_snapshot_id": snapshot_id,
        "document_artifact_ids": artifact_ids,
    }


def _refresh_claim_validation(*, job_state: JobState, package_state: PackageState) -> None:
    """Refresh claim validation list from match support heuristics."""

    plan = job_state.tailoring_plan or {}
    selected = [
        item
        for item in plan.get("items", [])
        if isinstance(item, dict) and bool(item.get("is_selected"))
    ]

    results: list[ClaimValidationResult] = []
    for item in selected:
        results.append(
            ClaimValidationResult(
                claim_text=str(item.get("text", "")),
                status="supported",
                evidence_keys=[str(item.get("fact_key", ""))],
                message="Selected from verified master-profile evidence.",
            )
        )

    for requirement in job_state.missing_requirements():
        results.append(
            ClaimValidationResult(
                claim_text=str(requirement.get("text", "")),
                status="missing",
                evidence_keys=[],
                message="No strong selected evidence found.",
            )
        )

    package_state.claim_validation = results


def _render_claim_validation_results(results: list[ClaimValidationResult]) -> None:
    """Render claim validation statuses."""

    with ui.card().classes("w-full"):
        ui.label("Claim Validation Results").classes("text-md font-semibold")
        if not results:
            ui.label("No claim validation entries yet.").classes("text-sm text-slate-600")
            return

        for item in results:
            badge_color = "positive" if item.status == "supported" else "negative"
            ui.badge(item.status.upper()).props(f"color={badge_color}")
            ui.label(item.claim_text or "-").classes("text-sm")
            if item.message:
                ui.label(item.message).classes("text-xs text-slate-600")


async def _render_document_previews(*, job_state: JobState, document_api: DocumentApi) -> None:
    """Render CV and cover-letter previews with evidence references."""

    snapshot = job_state.snapshot or {}
    evidence_refs = _build_evidence_references(job_state.tailoring_plan)

    cv_artifacts = job_state.generated_documents.get("cv", [])
    cover_artifacts = job_state.generated_documents.get("cover_letter", [])

    cv_preview = await _load_html_preview(artifacts=cv_artifacts, document_api=document_api)
    cover_preview = await _load_html_preview(artifacts=cover_artifacts, document_api=document_api)

    render_cv_preview(
        summary_text=str(snapshot.get("summary") or ""),
        evidence_refs=evidence_refs,
        html_preview=cv_preview,
    )
    render_cover_letter_preview(
        content_text=str(snapshot.get("summary") or ""),
        evidence_refs=evidence_refs,
        html_preview=cover_preview,
    )


async def _load_html_preview(*, artifacts: list[dict[str, Any]], document_api: DocumentApi) -> str | None:
    """Load HTML preview body for first html artifact."""

    for artifact in artifacts:
        if str(artifact.get("file_format")) != "html":
            continue
        artifact_id = str(artifact.get("id", ""))
        if not artifact_id:
            continue
        try:
            return await run.io_bound(lambda: document_api.get_document_text(artifact_id))
        except FrontendApiError:
            return None
    return None


def _render_export_links(*, job_state: JobState, document_api: DocumentApi) -> None:
    """Render export/download links for generated artifacts."""

    with ui.card().classes("w-full"):
        ui.label("Export Artifacts").classes("text-md font-semibold")

        artifact_rows = _flatten_artifacts(job_state.generated_documents)
        if not artifact_rows:
            ui.label("No artifacts generated yet.").classes("text-sm text-slate-600")
            return

        for artifact in artifact_rows:
            artifact_id = str(artifact.get("id", ""))
            file_name = str(artifact.get("file_name", "-"))
            file_format = str(artifact.get("file_format", "-"))
            with ui.row().classes("items-center gap-3"):
                ui.label(f"{file_name} ({file_format})").classes("text-sm")
                if artifact_id:
                    url = document_api.build_download_url(artifact_id)
                    ui.link("Download", target=url, new_tab=True).classes("text-primary")


def _build_output_warnings(*, job_state: JobState) -> list[str]:
    """Build warning list for output review phase."""

    warnings: list[str] = []
    if job_state.snapshot is None:
        warnings.append("No tailored snapshot loaded. Outputs cannot be generated yet.")

    missing_count = len(job_state.missing_requirements())
    if missing_count > 0:
        warnings.append(
            f"{missing_count} requirement(s) remain unsupported by selected evidence."
        )

    if not _flatten_artifacts(job_state.generated_documents):
        warnings.append("No generated artifacts available for export.")

    return warnings


def _build_evidence_references(plan: dict[str, Any] | None) -> list[str]:
    """Build evidence-reference labels from selected tailoring items."""

    if plan is None:
        return []

    references: list[str] = []
    for item in plan.get("items", []):
        if not isinstance(item, dict) or not item.get("is_selected"):
            continue
        fact_key = str(item.get("fact_key", "-"))
        reason = str(item.get("selection_reason", ""))
        references.append(f"{fact_key}: {reason}")
    return references


def _group_artifacts_by_type(raw_artifacts: Any) -> dict[str, list[dict[str, Any]]]:
    """Group document artifacts by document type field."""

    grouped: dict[str, list[dict[str, Any]]] = {"cv": [], "cover_letter": []}
    if not isinstance(raw_artifacts, list):
        return grouped

    for item in raw_artifacts:
        if not isinstance(item, dict):
            continue
        document_type = str(item.get("document_type", ""))
        if document_type not in grouped:
            continue
        grouped[document_type].append(item)
    return grouped


def _flatten_artifacts(
    grouped: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Flatten grouped document artifact mapping."""

    flattened: list[dict[str, Any]] = []
    for artifacts in grouped.values():
        flattened.extend(artifacts)
    return flattened
