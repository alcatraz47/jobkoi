"""Frontend state models for profile import workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportDecisionDraft:
    """Editable decision draft for one extracted field."""

    decision: str = "approve"
    edited_value: str | None = None
    reviewer_note: str | None = None


@dataclass
class ConflictResolutionDraft:
    """Editable resolution draft for one detected conflict."""

    resolution_status: str = "pending"
    resolution_note: str | None = None


@dataclass
class ProfileImportState:
    """State container for CV/website import run review workflow."""

    runs: list[dict[str, Any]] = field(default_factory=list)
    selected_run: dict[str, Any] | None = None
    field_decisions: dict[str, ImportDecisionDraft] = field(default_factory=dict)
    conflict_resolutions: dict[str, ConflictResolutionDraft] = field(default_factory=dict)

    def load_selected_run(self, run_payload: dict[str, Any]) -> None:
        """Load selected run payload and initialize draft decisions.

        Args:
            run_payload: Import run payload.
        """

        self.selected_run = run_payload
        self.field_decisions = {}
        self.conflict_resolutions = {}

        for field in run_payload.get("fields", []):
            if not isinstance(field, dict):
                continue
            field_id = str(field.get("id", ""))
            if not field_id:
                continue
            status = str(field.get("decision_status", "pending"))
            decision = _status_to_decision(status)
            suggested = field.get("suggested_value")
            self.field_decisions[field_id] = ImportDecisionDraft(
                decision=decision,
                edited_value=str(suggested) if suggested is not None else None,
                reviewer_note=None,
            )

        for conflict in run_payload.get("conflicts", []):
            if not isinstance(conflict, dict):
                continue
            conflict_id = str(conflict.get("id", ""))
            if not conflict_id:
                continue
            self.conflict_resolutions[conflict_id] = ConflictResolutionDraft(
                resolution_status=str(conflict.get("resolution_status", "pending")),
                resolution_note=str(conflict.get("resolution_note") or "") or None,
            )


def _status_to_decision(status: str) -> str:
    """Map field decision status values to editable decision labels."""

    if status == "approved":
        return "approve"
    if status == "rejected":
        return "reject"
    if status == "edited":
        return "edit"
    return "approve"
