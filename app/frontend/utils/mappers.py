"""Mapping helpers for frontend-to-backend payload transforms."""

from __future__ import annotations

from typing import Any

from app.frontend.state.profile_state import ProfileState


def build_profile_request_payload(profile_state: ProfileState) -> dict[str, Any]:
    """Build backend profile create/update payload from frontend state.

    Args:
        profile_state: Current profile state object.

    Returns:
        Backend-compatible profile payload.
    """

    return profile_state.to_backend_payload()


def build_job_post_payload(job_intake: dict[str, Any]) -> dict[str, Any]:
    """Build backend job post payload from intake dictionary.

    Args:
        job_intake: Frontend job intake dictionary.

    Returns:
        Backend-compatible job post payload.
    """

    return {
        "title": str(job_intake.get("title", "")),
        "company": job_intake.get("company"),
        "description": str(job_intake.get("description", "")),
    }
