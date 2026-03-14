"""Repository for profile persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.profile import (
    MasterProfileModel,
    MasterProfileVersionModel,
    ProfileEducationModel,
    ProfileExperienceModel,
    ProfileSkillModel,
)


@dataclass(frozen=True)
class ExperiencePayload:
    """Input payload for a profile experience row."""

    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None


@dataclass(frozen=True)
class EducationPayload:
    """Input payload for a profile education row."""

    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class SkillPayload:
    """Input payload for a profile skill row."""

    skill_name: str
    level: str | None
    category: str | None


@dataclass(frozen=True)
class ProfileVersionPayload:
    """Input payload for creating a new profile version."""

    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    experiences: list[ExperiencePayload]
    educations: list[EducationPayload]
    skills: list[SkillPayload]


class ProfileRepository:
    """Persistence operations for master profile and versions."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with an active SQLAlchemy session.

        Args:
            session: Active database session.
        """

        self._session = session

    def get_profile(self) -> MasterProfileModel | None:
        """Return the singleton master profile if present.

        Returns:
            Existing master profile, or None when missing.
        """

        stmt = select(MasterProfileModel).limit(1)
        return self._session.scalar(stmt)

    def create_profile(self) -> MasterProfileModel:
        """Create a new master profile record.

        Returns:
            Newly created master profile ORM object.
        """

        profile = MasterProfileModel()
        self._session.add(profile)
        self._session.flush()
        return profile

    def delete_profile(self, profile: MasterProfileModel) -> None:
        """Delete a master profile record.

        Args:
            profile: Master profile to remove.
        """

        self._session.delete(profile)
        self._session.flush()

    def get_next_version_number(self, profile_id: str) -> int:
        """Return the next version number for a profile.

        Args:
            profile_id: Master profile identifier.

        Returns:
            Next sequential version number.
        """

        stmt = select(func.max(MasterProfileVersionModel.version_number)).where(
            MasterProfileVersionModel.master_profile_id == profile_id
        )
        max_version = self._session.scalar(stmt)
        return 1 if max_version is None else int(max_version) + 1

    def create_profile_version(
        self,
        profile_id: str,
        payload: ProfileVersionPayload,
    ) -> MasterProfileVersionModel:
        """Persist a new immutable profile version and child rows.

        Args:
            profile_id: Master profile identifier.
            payload: Version payload with nested section entries.

        Returns:
            Newly created profile version ORM object.
        """

        version = MasterProfileVersionModel(
            master_profile_id=profile_id,
            version_number=self.get_next_version_number(profile_id),
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            location=payload.location,
            headline=payload.headline,
            summary=payload.summary,
            experiences=self._build_experience_rows(payload.experiences),
            educations=self._build_education_rows(payload.educations),
            skills=self._build_skill_rows(payload.skills),
        )
        self._session.add(version)
        self._session.flush()
        return version

    def set_active_version(self, profile: MasterProfileModel, version_id: str) -> None:
        """Set the active version pointer on a master profile.

        Args:
            profile: Master profile record.
            version_id: Version identifier to mark as active.
        """

        profile.active_version_id = version_id
        self._session.add(profile)
        self._session.flush()

    def get_profile_version(
        self,
        profile_id: str,
        version_id: str,
    ) -> MasterProfileVersionModel | None:
        """Fetch one profile version with child rows loaded.

        Args:
            profile_id: Parent profile identifier.
            version_id: Version identifier.

        Returns:
            Matching profile version, or None when missing.
        """

        stmt = (
            select(MasterProfileVersionModel)
            .where(
                MasterProfileVersionModel.id == version_id,
                MasterProfileVersionModel.master_profile_id == profile_id,
            )
            .options(
                selectinload(MasterProfileVersionModel.experiences),
                selectinload(MasterProfileVersionModel.educations),
                selectinload(MasterProfileVersionModel.skills),
            )
        )
        return self._session.scalar(stmt)

    def get_profile_version_by_id(self, version_id: str) -> MasterProfileVersionModel | None:
        """Fetch one profile version by identifier with child rows loaded.

        Args:
            version_id: Version identifier.

        Returns:
            Matching profile version, or None when missing.
        """

        stmt = (
            select(MasterProfileVersionModel)
            .where(MasterProfileVersionModel.id == version_id)
            .options(
                selectinload(MasterProfileVersionModel.experiences),
                selectinload(MasterProfileVersionModel.educations),
                selectinload(MasterProfileVersionModel.skills),
            )
        )
        return self._session.scalar(stmt)

    def list_profile_versions(self, profile_id: str) -> list[MasterProfileVersionModel]:
        """List profile versions in descending version order.

        Args:
            profile_id: Parent profile identifier.

        Returns:
            Ordered profile versions for the profile.
        """

        stmt = (
            select(MasterProfileVersionModel)
            .where(MasterProfileVersionModel.master_profile_id == profile_id)
            .order_by(MasterProfileVersionModel.version_number.desc())
            .options(
                selectinload(MasterProfileVersionModel.experiences),
                selectinload(MasterProfileVersionModel.educations),
                selectinload(MasterProfileVersionModel.skills),
            )
        )
        return list(self._session.scalars(stmt).all())

    @staticmethod
    def _build_experience_rows(entries: list[ExperiencePayload]) -> list[ProfileExperienceModel]:
        """Build ORM experience rows from payload entries.

        Args:
            entries: Experience payload rows.

        Returns:
            Experience ORM row list.
        """

        rows: list[ProfileExperienceModel] = []
        for index, entry in enumerate(entries):
            rows.append(
                ProfileExperienceModel(
                    company=entry.company,
                    title=entry.title,
                    start_date=entry.start_date,
                    end_date=entry.end_date,
                    description=entry.description,
                    sort_order=index,
                )
            )
        return rows

    @staticmethod
    def _build_education_rows(entries: list[EducationPayload]) -> list[ProfileEducationModel]:
        """Build ORM education rows from payload entries.

        Args:
            entries: Education payload rows.

        Returns:
            Education ORM row list.
        """

        rows: list[ProfileEducationModel] = []
        for index, entry in enumerate(entries):
            rows.append(
                ProfileEducationModel(
                    institution=entry.institution,
                    degree=entry.degree,
                    field_of_study=entry.field_of_study,
                    start_date=entry.start_date,
                    end_date=entry.end_date,
                    sort_order=index,
                )
            )
        return rows

    @staticmethod
    def _build_skill_rows(entries: list[SkillPayload]) -> list[ProfileSkillModel]:
        """Build ORM skill rows from payload entries.

        Args:
            entries: Skill payload rows.

        Returns:
            Skill ORM row list.
        """

        rows: list[ProfileSkillModel] = []
        for index, entry in enumerate(entries):
            rows.append(
                ProfileSkillModel(
                    skill_name=entry.skill_name,
                    level=entry.level,
                    category=entry.category,
                    sort_order=index,
                )
            )
        return rows
