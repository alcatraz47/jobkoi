"""Certification section form component."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app.frontend.state.profile_state import CertificationEntry, ProfileState


def render_certification_form(profile_state: ProfileState) -> None:
    """Render editable certification list.

    Args:
        profile_state: Mutable profile state object.

    Returns:
        None.
    """

    ui.label("Certifications").classes("text-md font-semibold")
    container = ui.column().classes("w-full gap-2")

    def refresh() -> None:
        container.clear()
        with container:
            if not profile_state.draft.certifications:
                ui.label("No certifications added yet.").classes("text-sm text-slate-500")
            for index, item in enumerate(profile_state.draft.certifications):
                _render_certification_card(profile_state, index, item, refresh)

    ui.button("Add Certification", on_click=lambda: _add_certification(profile_state, refresh)).props("outline")
    refresh()


def _render_certification_card(
    profile_state: ProfileState,
    index: int,
    item: CertificationEntry,
    refresh: Callable[[], None],
) -> None:
    """Render one certification item card."""

    with ui.card().classes("w-full"):
        ui.input("Certification Name", value=item.name, on_change=lambda e, i=index: _set_name(profile_state, i, e.value))
        ui.input("Issuer", value=item.issuer or "", on_change=lambda e, i=index: _set_issuer(profile_state, i, e.value))
        ui.input(
            "Issue Date",
            value=item.issue_date or "",
            on_change=lambda e, i=index: _set_issue_date(profile_state, i, e.value),
        )
        ui.input(
            "Credential ID",
            value=item.credential_id or "",
            on_change=lambda e, i=index: _set_credential_id(profile_state, i, e.value),
        )
        ui.button("Delete", on_click=lambda _, i=index: _delete_certification(profile_state, i, refresh)).props("flat color=negative")


def _add_certification(profile_state: ProfileState, refresh: Callable[[], None]) -> None:
    """Append one empty certification item."""

    profile_state.draft.certifications.append(CertificationEntry())
    refresh()


def _delete_certification(profile_state: ProfileState, index: int, refresh: Callable[[], None]) -> None:
    """Delete one certification item by index."""

    del profile_state.draft.certifications[index]
    refresh()


def _set_name(profile_state: ProfileState, index: int, value: str) -> None:
    """Set certification name."""

    profile_state.draft.certifications[index].name = value


def _set_issuer(profile_state: ProfileState, index: int, value: str) -> None:
    """Set certification issuer."""

    profile_state.draft.certifications[index].issuer = value or None


def _set_issue_date(profile_state: ProfileState, index: int, value: str) -> None:
    """Set certification issue date."""

    profile_state.draft.certifications[index].issue_date = value or None


def _set_credential_id(profile_state: ProfileState, index: int, value: str) -> None:
    """Set certification credential id."""

    profile_state.draft.certifications[index].credential_id = value or None
