"""NiceGUI frontend bootstrap and page registration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from fastapi import FastAPI
from nicegui import ui

from app.frontend.pages.application_packages_page import register_application_packages_page
from app.frontend.pages.dashboard_page import register_dashboard_page
from app.frontend.pages.job_intake_page import register_job_intake_page
from app.frontend.pages.match_review_page import register_match_review_page
from app.frontend.pages.output_review_page import register_output_review_page
from app.frontend.pages.profile_page import register_profile_page
from app.frontend.services.application_package_api import ApplicationPackageApi
from app.frontend.services.document_api import DocumentApi
from app.frontend.services.job_post_api import JobPostApi
from app.frontend.services.profile_api import ProfileApi
from app.frontend.services.tailoring_api import TailoringApi
from app.frontend.state.job_state import JobState
from app.frontend.state.package_state import PackageState
from app.frontend.state.profile_state import ProfileState
from app.frontend.state.session_state import FrontendSessionState


@dataclass
class FrontendRuntime:
    """Container for shared frontend state and service adapters."""

    profile_state: ProfileState = field(default_factory=ProfileState)
    job_state: JobState = field(default_factory=JobState)
    package_state: PackageState = field(default_factory=PackageState)
    session_state: FrontendSessionState = field(default_factory=FrontendSessionState)
    profile_api: ProfileApi = field(default_factory=ProfileApi)
    job_post_api: JobPostApi = field(default_factory=JobPostApi)
    tailoring_api: TailoringApi = field(default_factory=TailoringApi)
    document_api: DocumentApi = field(default_factory=DocumentApi)
    package_api: ApplicationPackageApi = field(default_factory=ApplicationPackageApi)


_PAGES_REGISTERED = False
_FRONTEND_MOUNTED = False


def register_frontend(fastapi_app: FastAPI) -> None:
    """Register NiceGUI frontend pages and mount them into FastAPI.

    Args:
        fastapi_app: Existing FastAPI application.

    Returns:
        None.
    """

    global _PAGES_REGISTERED
    global _FRONTEND_MOUNTED

    if _is_pytest_runtime() or _FRONTEND_MOUNTED:
        return

    if not _PAGES_REGISTERED:
        runtime = FrontendRuntime()
        _register_pages(runtime)
        _PAGES_REGISTERED = True

    try:
        ui.run_with(
            fastapi_app,
            title="Jobkoi",
            mount_path="/",
            storage_secret="jobkoi-local-storage-secret",
        )
    except RuntimeError:
        # NiceGUI can only mount once after middleware setup has started.
        _FRONTEND_MOUNTED = True
        return

    _FRONTEND_MOUNTED = True


def _register_pages(runtime: FrontendRuntime) -> None:
    """Register all frontend page modules."""

    register_dashboard_page(
        profile_state=runtime.profile_state,
        package_state=runtime.package_state,
        profile_api=runtime.profile_api,
        package_api=runtime.package_api,
    )
    register_profile_page(
        profile_state=runtime.profile_state,
        profile_api=runtime.profile_api,
    )
    register_job_intake_page(
        job_state=runtime.job_state,
        session_state=runtime.session_state,
        job_post_api=runtime.job_post_api,
    )
    register_match_review_page(
        profile_state=runtime.profile_state,
        job_state=runtime.job_state,
        session_state=runtime.session_state,
        job_post_api=runtime.job_post_api,
        tailoring_api=runtime.tailoring_api,
    )
    register_output_review_page(
        job_state=runtime.job_state,
        package_state=runtime.package_state,
        session_state=runtime.session_state,
        tailoring_api=runtime.tailoring_api,
        document_api=runtime.document_api,
        package_api=runtime.package_api,
    )
    register_application_packages_page(
        package_state=runtime.package_state,
        session_state=runtime.session_state,
        package_api=runtime.package_api,
        document_api=runtime.document_api,
    )


def _is_pytest_runtime() -> bool:
    """Return True when app is running under pytest."""

    return "PYTEST_CURRENT_TEST" in os.environ
