"""Business service for master profile operations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.profile import (
    MasterProfileModel,
    MasterProfileVersionModel,
    ProfileEducationModel,
    ProfileExperienceModel,
    ProfileSkillModel,
)
from app.db.repositories.profile_repository import (
    EducationPayload,
    ExperiencePayload,
    ProfileRepository,
    ProfileVersionPayload,
    SkillPayload,
)
from app.schemas.profile import (
    DeleteProfileResponse,
    EducationInput,
    EducationResponse,
    ExperienceInput,
    ExperienceResponse,
    MasterProfileCreateRequest,
    MasterProfileResponse,
    MasterProfileUpdateRequest,
    MasterProfileVersionListResponse,
    MasterProfileVersionResponse,
    SkillInput,
    SkillResponse,
)


class ProfileNotFoundError(Exception):
    """Raised when the requested profile data is missing."""


class ProfileAlreadyExistsError(Exception):
    """Raised when trying to create a second master profile."""


class ProfileService:
    """Service coordinating profile persistence and versioning behavior."""

    def __init__(self, session: Session) -> None:
        """Initialize service with a database session.

        Args:
            session: Active SQLAlchemy session.
        """

        self._session = session
        self._repository = ProfileRepository(session)

    def create_profile(self, request: MasterProfileCreateRequest) -> MasterProfileResponse:
        """Create the singleton master profile and first version.

        Args:
            request: Profile creation payload.

        Returns:
            Created profile response with active version.

        Raises:
            ProfileAlreadyExistsError: If a master profile already exists.
        """

        if self._repository.get_profile() is not None:
            raise ProfileAlreadyExistsError("Master profile already exists.")

        profile = self._repository.create_profile()
        payload = self._to_version_payload(
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            location=request.location,
            headline=request.headline,
            summary=request.summary,
            experiences=request.experiences,
            educations=request.educations,
            skills=request.skills,
        )
        version = self._repository.create_profile_version(profile.id, payload)
        self._repository.set_active_version(profile, version.id)
        self._session.commit()
        return self.get_profile()

    def get_profile(self) -> MasterProfileResponse:
        """Get the active master profile and active version.

        Returns:
            Active profile response payload.

        Raises:
            ProfileNotFoundError: If no profile or active version exists.
        """

        profile = self._require_profile()
        if profile.active_version_id is None:
            raise ProfileNotFoundError("Active profile version not found.")

        version = self._repository.get_profile_version(profile.id, profile.active_version_id)
        if version is None:
            raise ProfileNotFoundError("Active profile version not found.")

        return MasterProfileResponse(
            profile_id=profile.id,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            active_version=self._to_version_response(version),
        )

    def update_profile(self, request: MasterProfileUpdateRequest) -> MasterProfileResponse:
        """Create a new active profile version from update input.

        Args:
            request: Profile update payload.

        Returns:
            Updated active profile response.

        Raises:
            ProfileNotFoundError: If no existing profile exists.
        """

        profile = self._require_profile()
        payload = self._to_version_payload(
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            location=request.location,
            headline=request.headline,
            summary=request.summary,
            experiences=request.experiences,
            educations=request.educations,
            skills=request.skills,
        )
        version = self._repository.create_profile_version(profile.id, payload)
        self._repository.set_active_version(profile, version.id)
        self._session.commit()
        return self.get_profile()

    def delete_profile(self) -> DeleteProfileResponse:
        """Delete the master profile and all versions.

        Returns:
            Deletion acknowledgement response.

        Raises:
            ProfileNotFoundError: If no profile exists.
        """

        profile = self._require_profile()
        self._repository.delete_profile(profile)
        self._session.commit()
        return DeleteProfileResponse(deleted=True)

    def list_profile_versions(self) -> MasterProfileVersionListResponse:
        """List profile version history for the master profile.

        Returns:
            Profile version listing payload.

        Raises:
            ProfileNotFoundError: If no profile exists.
        """

        profile = self._require_profile()
        versions = self._repository.list_profile_versions(profile.id)
        version_items = [self._to_version_response(version) for version in versions]
        return MasterProfileVersionListResponse(profile_id=profile.id, versions=version_items)

    def get_profile_version(self, version_id: str) -> MasterProfileVersionResponse:
        """Get one specific profile version.

        Args:
            version_id: Version identifier.

        Returns:
            Profile version response.

        Raises:
            ProfileNotFoundError: If profile or version does not exist.
        """

        profile = self._require_profile()
        version = self._repository.get_profile_version(profile.id, version_id)
        if version is None:
            raise ProfileNotFoundError("Profile version not found.")
        return self._to_version_response(version)

    def _require_profile(self) -> MasterProfileModel:
        """Load the singleton profile and fail when absent.

        Returns:
            Master profile ORM object.

        Raises:
            ProfileNotFoundError: If no profile exists.
        """

        profile = self._repository.get_profile()
        if profile is None:
            raise ProfileNotFoundError("Master profile not found.")
        return profile

    @staticmethod
    def _to_version_payload(
        *,
        full_name: str,
        email: str,
        phone: str | None,
        location: str | None,
        headline: str | None,
        summary: str | None,
        experiences: list[ExperienceInput],
        educations: list[EducationInput],
        skills: list[SkillInput],
    ) -> ProfileVersionPayload:
        """Map API input data to repository version payload.

        Args:
            full_name: Candidate full name.
            email: Candidate email.
            phone: Candidate phone.
            location: Candidate location.
            headline: Candidate headline.
            summary: Candidate summary.
            experiences: Experience input entries.
            educations: Education input entries.
            skills: Skill input entries.

        Returns:
            Repository-ready profile version payload.
        """

        mapped_experiences = [
            ExperiencePayload(
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
            )
            for item in experiences
        ]
        mapped_educations = [
            EducationPayload(
                institution=item.institution,
                degree=item.degree,
                field_of_study=item.field_of_study,
                start_date=item.start_date,
                end_date=item.end_date,
            )
            for item in educations
        ]
        mapped_skills = [
            SkillPayload(skill_name=item.skill_name, level=item.level, category=item.category)
            for item in skills
        ]
        return ProfileVersionPayload(
            full_name=full_name,
            email=email,
            phone=phone,
            location=location,
            headline=headline,
            summary=summary,
            experiences=mapped_experiences,
            educations=mapped_educations,
            skills=mapped_skills,
        )

    @staticmethod
    def _to_version_response(version: MasterProfileVersionModel) -> MasterProfileVersionResponse:
        """Map a profile version ORM object to response schema.

        Args:
            version: Profile version ORM object.

        Returns:
            Version response schema.
        """

        return MasterProfileVersionResponse(
            version_id=version.id,
            profile_id=version.master_profile_id,
            version_number=version.version_number,
            full_name=version.full_name,
            email=version.email,
            phone=version.phone,
            location=version.location,
            headline=version.headline,
            summary=version.summary,
            created_at=version.created_at,
            experiences=[ProfileService._to_experience_response(item) for item in version.experiences],
            educations=[ProfileService._to_education_response(item) for item in version.educations],
            skills=[ProfileService._to_skill_response(item) for item in version.skills],
        )

    @staticmethod
    def _to_experience_response(item: ProfileExperienceModel) -> ExperienceResponse:
        """Map ORM experience row to response schema.

        Args:
            item: ORM experience row.

        Returns:
            Experience response schema.
        """

        return ExperienceResponse(
            id=item.id,
            company=item.company,
            title=item.title,
            start_date=item.start_date,
            end_date=item.end_date,
            description=item.description,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _to_education_response(item: ProfileEducationModel) -> EducationResponse:
        """Map ORM education row to response schema.

        Args:
            item: ORM education row.

        Returns:
            Education response schema.
        """

        return EducationResponse(
            id=item.id,
            institution=item.institution,
            degree=item.degree,
            field_of_study=item.field_of_study,
            start_date=item.start_date,
            end_date=item.end_date,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _to_skill_response(item: ProfileSkillModel) -> SkillResponse:
        """Map ORM skill row to response schema.

        Args:
            item: ORM skill row.

        Returns:
            Skill response schema.
        """

        return SkillResponse(
            id=item.id,
            skill_name=item.skill_name,
            level=item.level,
            category=item.category,
            sort_order=item.sort_order,
        )
