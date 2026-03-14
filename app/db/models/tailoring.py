"""ORM models for tailoring plans and tailored profile snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Returns:
        The current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class TailoringPlanModel(Base):
    """Stored deterministic tailoring plan."""

    __tablename__ = "tailoring_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_analyses.id", ondelete="CASCADE"), nullable=False
    )
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="CASCADE"), nullable=False
    )
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    items: Mapped[list[TailoringPlanItemModel]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="TailoringPlanItemModel.relevance_score.desc()",
    )
    snapshots: Mapped[list[ProfileSnapshotModel]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class TailoringPlanItemModel(Base):
    """Scored and selected fact entry in a tailoring plan."""

    __tablename__ = "tailoring_plan_items"
    __table_args__ = (
        UniqueConstraint("tailoring_plan_id", "fact_key", name="uq_tailoring_plan_fact_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tailoring_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tailoring_plans.id", ondelete="CASCADE"), nullable=False
    )
    fact_key: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    plan: Mapped[TailoringPlanModel] = relationship(back_populates="items")


class ProfileSnapshotModel(Base):
    """Immutable tailored profile snapshot for one target application."""

    __tablename__ = "profile_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tailoring_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tailoring_plans.id", ondelete="CASCADE"), nullable=False
    )
    profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_profile_versions.id", ondelete="CASCADE"), nullable=False
    )
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    plan: Mapped[TailoringPlanModel] = relationship(back_populates="snapshots")
    experiences: Mapped[list[SnapshotExperienceModel]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotExperienceModel.sort_order",
    )
    educations: Mapped[list[SnapshotEducationModel]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotEducationModel.sort_order",
    )
    skills: Mapped[list[SnapshotSkillModel]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotSkillModel.sort_order",
    )


class SnapshotExperienceModel(Base):
    """Experience entry copied into a profile snapshot."""

    __tablename__ = "snapshot_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profile_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_experience_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped[ProfileSnapshotModel] = relationship(back_populates="experiences")


class SnapshotEducationModel(Base):
    """Education entry copied into a profile snapshot."""

    __tablename__ = "snapshot_educations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profile_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_education_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped[ProfileSnapshotModel] = relationship(back_populates="educations")


class SnapshotSkillModel(Base):
    """Skill entry copied into a profile snapshot."""

    __tablename__ = "snapshot_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profile_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped[ProfileSnapshotModel] = relationship(back_populates="skills")
