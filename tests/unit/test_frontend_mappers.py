"""Unit tests for frontend payload mapping helpers."""

from __future__ import annotations

from app.frontend.state.profile_state import ProfileState
from app.frontend.utils.mappers import build_job_post_payload, build_profile_request_payload


def test_build_profile_request_payload_uses_state_mapper() -> None:
    """Profile mapper helper should delegate to state backend payload mapping."""

    state = ProfileState()
    state.draft.full_name = "Ada"
    state.draft.email = "ada@example.com"

    payload = build_profile_request_payload(state)

    assert payload["full_name"] == "Ada"
    assert payload["email"] == "ada@example.com"


def test_build_job_post_payload_maps_expected_keys() -> None:
    """Job mapper should return backend-compatible title/company/description payload."""

    payload = build_job_post_payload(
        {
            "title": "Backend Engineer",
            "company": "Example GmbH",
            "description": "Build and maintain APIs.",
            "language": "de",
        }
    )

    assert payload == {
        "title": "Backend Engineer",
        "company": "Example GmbH",
        "description": "Build and maintain APIs.",
    }
