"""Centralized frontend labels and warning copy."""

from __future__ import annotations


MISSING_REQUIREMENT_WARNING = "Requirement is not supported by selected profile evidence."
WEAK_EVIDENCE_WARNING = "Requirement has weak support and should be reviewed before export."
MASTER_PROFILE_BADGE = "Viewing: Master Profile"
SNAPSHOT_PROFILE_BADGE = "Viewing: Tailored Snapshot"

LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("English", "en"),
    ("German", "de"),
]
