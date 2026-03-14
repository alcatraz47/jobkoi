"""Repository for tailoring plan and profile snapshot persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.tailoring import (
    ProfileSnapshotModel,
    SnapshotEducationModel,
    SnapshotExperienceModel,
    SnapshotSkillModel,
    TailoringPlanItemModel,
    TailoringPlanModel,
)


@dataclass(frozen=True)
class TailoringPlanItemPayload:
    """Payload for one tailoring plan fact entry."""

    fact_key: str
    fact_type: str
    source_entity_id: str | None
    source_text: str
    relevance_score: int
    is_selected: bool
    selection_reason: str


@dataclass(frozen=True)
class TailoringPlanCreatePayload:
    """Payload for creating a tailoring plan."""

    job_analysis_id: str
    profile_version_id: str
    target_language: str
    summary: str
    items: list[TailoringPlanItemPayload]


@dataclass(frozen=True)
class SnapshotExperiencePayload:
    """Payload for one snapshot experience row."""

    source_experience_id: str | None
    company: str
    title: str
    start_date: date | None
    end_date: date | None
    description: str | None
    relevance_score: int


@dataclass(frozen=True)
class SnapshotEducationPayload:
    """Payload for one snapshot education row."""

    source_education_id: str | None
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    relevance_score: int


@dataclass(frozen=True)
class SnapshotSkillPayload:
    """Payload for one snapshot skill row."""

    source_skill_id: str | None
    skill_name: str
    level: str | None
    category: str | None
    relevance_score: int


@dataclass(frozen=True)
class ProfileSnapshotCreatePayload:
    """Payload for creating an immutable tailored profile snapshot."""

    tailoring_plan_id: str
    profile_version_id: str
    target_language: str
    full_name: str
    email: str
    phone: str | None
    location: str | None
    headline: str | None
    summary: str | None
    experiences: list[SnapshotExperiencePayload]
    educations: list[SnapshotEducationPayload]
    skills: list[SnapshotSkillPayload]


class TailoringRepository:
    """Persistence operations for tailoring plans and snapshots."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: Active SQLAlchemy session.
        """

        self._session = session

    def create_plan(self, payload: TailoringPlanCreatePayload) -> TailoringPlanModel:
        """Create and persist a tailoring plan.

        Args:
            payload: Tailoring plan payload.

        Returns:
            Persisted tailoring plan model with item rows.
        """

        items = [
            TailoringPlanItemModel(
                fact_key=item.fact_key,
                fact_type=item.fact_type,
                source_entity_id=item.source_entity_id,
                source_text=item.source_text,
                relevance_score=item.relevance_score,
                is_selected=item.is_selected,
                selection_reason=item.selection_reason,
            )
            for item in payload.items
        ]

        plan = TailoringPlanModel(
            job_analysis_id=payload.job_analysis_id,
            profile_version_id=payload.profile_version_id,
            target_language=payload.target_language,
            summary=payload.summary,
            items=items,
        )
        self._session.add(plan)
        self._session.flush()
        return plan

    def get_plan(self, plan_id: str) -> TailoringPlanModel | None:
        """Fetch a tailoring plan by identifier.

        Args:
            plan_id: Tailoring plan identifier.

        Returns:
            Tailoring plan model with item rows when found.
        """

        stmt = (
            select(TailoringPlanModel)
            .where(TailoringPlanModel.id == plan_id)
            .options(selectinload(TailoringPlanModel.items))
        )
        return self._session.scalar(stmt)

    def create_snapshot(self, payload: ProfileSnapshotCreatePayload) -> ProfileSnapshotModel:
        """Create and persist a tailored profile snapshot.

        Args:
            payload: Snapshot payload.

        Returns:
            Persisted snapshot model with copied child rows.
        """

        snapshot = ProfileSnapshotModel(
            tailoring_plan_id=payload.tailoring_plan_id,
            profile_version_id=payload.profile_version_id,
            target_language=payload.target_language,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            location=payload.location,
            headline=payload.headline,
            summary=payload.summary,
            experiences=self._build_snapshot_experiences(payload.experiences),
            educations=self._build_snapshot_educations(payload.educations),
            skills=self._build_snapshot_skills(payload.skills),
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> ProfileSnapshotModel | None:
        """Fetch a profile snapshot by identifier.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Snapshot model with copied section rows when found.
        """

        stmt = (
            select(ProfileSnapshotModel)
            .where(ProfileSnapshotModel.id == snapshot_id)
            .options(
                selectinload(ProfileSnapshotModel.experiences),
                selectinload(ProfileSnapshotModel.educations),
                selectinload(ProfileSnapshotModel.skills),
            )
        )
        return self._session.scalar(stmt)

    @staticmethod
    def _build_snapshot_experiences(
        entries: list[SnapshotExperiencePayload],
    ) -> list[SnapshotExperienceModel]:
        """Map snapshot experience payload rows to ORM entities."""

        return [
            SnapshotExperienceModel(
                source_experience_id=item.source_experience_id,
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
                relevance_score=item.relevance_score,
                sort_order=index,
            )
            for index, item in enumerate(entries)
        ]

    @staticmethod
    def _build_snapshot_educations(
        entries: list[SnapshotEducationPayload],
    ) -> list[SnapshotEducationModel]:
        """Map snapshot education payload rows to ORM entities."""

        return [
            SnapshotEducationModel(
                source_education_id=item.source_education_id,
                institution=item.institution,
                degree=item.degree,
                field_of_study=item.field_of_study,
                start_date=item.start_date,
                end_date=item.end_date,
                relevance_score=item.relevance_score,
                sort_order=index,
            )
            for index, item in enumerate(entries)
        ]

    @staticmethod
    def _build_snapshot_skills(entries: list[SnapshotSkillPayload]) -> list[SnapshotSkillModel]:
        """Map snapshot skill payload rows to ORM entities."""

        return [
            SnapshotSkillModel(
                source_skill_id=item.source_skill_id,
                skill_name=item.skill_name,
                level=item.level,
                category=item.category,
                relevance_score=item.relevance_score,
                sort_order=index,
            )
            for index, item in enumerate(entries)
        ]
