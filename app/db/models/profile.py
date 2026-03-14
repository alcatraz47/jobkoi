"""ORM models for master profile and versioned profile data."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Returns:
        The current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class MasterProfileModel(Base):
    """Canonical profile root entity.

    Attributes:
        id: Primary identifier for the profile.
        active_version_id: Identifier of the currently active profile version.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        versions: All profile versions belonging to this master profile.
        active_version: Currently active version relationship.
    """

    __tablename__ = "master_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    active_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="SET NULL", use_alter=True, name="fk_master_profiles_active_version_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    versions: Mapped[list[MasterProfileVersionModel]] = relationship(
        back_populates="master_profile",
        cascade="all, delete-orphan",
        foreign_keys="MasterProfileVersionModel.master_profile_id",
        order_by="MasterProfileVersionModel.version_number",
    )
    active_version: Mapped[MasterProfileVersionModel | None] = relationship(
        foreign_keys=[active_version_id],
        uselist=False,
        post_update=True,
    )


class MasterProfileVersionModel(Base):
    """Immutable profile version entity.

    Attributes:
        id: Primary identifier for the profile version.
        master_profile_id: Parent profile identifier.
        version_number: Sequential version number.
        full_name: Candidate full name.
        email: Candidate email address.
        phone: Candidate phone number.
        location: Candidate location.
        headline: Optional profile headline.
        summary: Optional professional summary.
        created_at: Creation timestamp.
        master_profile: Parent master profile relationship.
        experiences: Versioned experience records.
        educations: Versioned education records.
        skills: Versioned skill records.
    """

    __tablename__ = "master_profile_versions"
    __table_args__ = (
        UniqueConstraint("master_profile_id", "version_number", name="uq_profile_version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    master_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profiles.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    master_profile: Mapped[MasterProfileModel] = relationship(
        back_populates="versions",
        foreign_keys=[master_profile_id],
    )
    experiences: Mapped[list[ProfileExperienceModel]] = relationship(
        back_populates="profile_version",
        cascade="all, delete-orphan",
        order_by="ProfileExperienceModel.sort_order",
    )
    educations: Mapped[list[ProfileEducationModel]] = relationship(
        back_populates="profile_version",
        cascade="all, delete-orphan",
        order_by="ProfileEducationModel.sort_order",
    )
    skills: Mapped[list[ProfileSkillModel]] = relationship(
        back_populates="profile_version",
        cascade="all, delete-orphan",
        order_by="ProfileSkillModel.sort_order",
    )


class ProfileExperienceModel(Base):
    """Versioned professional experience entry."""

    __tablename__ = "master_profile_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="CASCADE"), nullable=False
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile_version: Mapped[MasterProfileVersionModel] = relationship(back_populates="experiences")


class ProfileEducationModel(Base):
    """Versioned education entry."""

    __tablename__ = "master_profile_educations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="CASCADE"), nullable=False
    )
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile_version: Mapped[MasterProfileVersionModel] = relationship(back_populates="educations")


class ProfileSkillModel(Base):
    """Versioned skill entry."""

    __tablename__ = "master_profile_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile_version: Mapped[MasterProfileVersionModel] = relationship(back_populates="skills")
