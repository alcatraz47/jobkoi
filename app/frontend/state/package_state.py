"""Frontend state models for application package browsing and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClaimValidationResult:
    """Frontend representation of claim validation status for output review."""

    claim_text: str
    status: str
    evidence_keys: list[str] = field(default_factory=list)
    message: str | None = None


@dataclass
class PackageState:
    """State container for package list and selected package details."""

    packages: list[dict[str, Any]] = field(default_factory=list)
    selected_package: dict[str, Any] | None = None
    claim_validation: list[ClaimValidationResult] = field(default_factory=list)

    def recent_packages(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return most recent package rows for dashboard display.

        Args:
            limit: Maximum number of package rows.

        Returns:
            Sliced package list.
        """

        return self.packages[:limit]
