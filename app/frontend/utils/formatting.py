"""Formatting helpers for frontend display text."""

from __future__ import annotations

from datetime import datetime


def format_datetime(value: str | None) -> str:
    """Format ISO datetime strings into compact readable values.

    Args:
        value: ISO datetime string.

    Returns:
        Human-readable datetime string, or ``-`` when missing.
    """

    if not value:
        return "-"

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def join_non_empty(parts: list[str | None], separator: str = " • ") -> str:
    """Join non-empty text parts using a separator.

    Args:
        parts: Candidate text values.
        separator: String separator.

    Returns:
        Joined non-empty text.
    """

    cleaned = [part.strip() for part in parts if part and part.strip()]
    return separator.join(cleaned)
