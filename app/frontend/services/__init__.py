"""Frontend service adapter package exports."""

from app.frontend.services.api_client import ApiClient, FrontendApiError, build_default_api_client
from app.frontend.services.application_package_api import ApplicationPackageApi
from app.frontend.services.document_api import DocumentApi
from app.frontend.services.job_post_api import JobPostApi
from app.frontend.services.profile_api import ProfileApi
from app.frontend.services.profile_import_api import ProfileImportApi
from app.frontend.services.tailoring_api import TailoringApi

__all__ = [
    "ApiClient",
    "FrontendApiError",
    "build_default_api_client",
    "ProfileApi",
    "ProfileImportApi",
    "JobPostApi",
    "TailoringApi",
    "DocumentApi",
    "ApplicationPackageApi",
]
