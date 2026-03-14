"""Repositories for job ingestion and analysis persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.job import JobAnalysisModel, JobPostModel, JobRequirementModel


@dataclass(frozen=True)
class JobPostCreatePayload:
    """Payload for persisting a job post."""

    title: str
    company: str | None
    description_raw: str
    normalized_description: str
    detected_language: str


@dataclass(frozen=True)
class JobRequirementPayload:
    """Payload for persisting one extracted requirement."""

    text: str
    normalized_text: str
    requirement_type: str
    is_must_have: bool
    priority_score: int
    source: str


@dataclass(frozen=True)
class JobAnalysisCreatePayload:
    """Payload for persisting a structured job analysis."""

    normalized_title: str
    detected_language: str
    summary: str
    requirements: list[JobRequirementPayload]


class JobPostRepository:
    """Persistence operations for job posts."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with a database session.

        Args:
            session: Active database session.
        """

        self._session = session

    def create(self, payload: JobPostCreatePayload) -> JobPostModel:
        """Persist a new job post.

        Args:
            payload: Job post data.

        Returns:
            Persisted job post ORM object.
        """

        model = JobPostModel(
            title=payload.title,
            company=payload.company,
            description_raw=payload.description_raw,
            normalized_description=payload.normalized_description,
            detected_language=payload.detected_language,
        )
        self._session.add(model)
        self._session.flush()
        return model

    def get(self, job_post_id: str) -> JobPostModel | None:
        """Fetch a job post by identifier.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Job post model when found, otherwise None.
        """

        stmt = select(JobPostModel).where(JobPostModel.id == job_post_id)
        return self._session.scalar(stmt)


class JobAnalysisRepository:
    """Persistence operations for job analyses and extracted requirements."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with a database session.

        Args:
            session: Active database session.
        """

        self._session = session

    def create(self, job_post_id: str, payload: JobAnalysisCreatePayload) -> JobAnalysisModel:
        """Persist a new structured job analysis.

        Args:
            job_post_id: Parent job post identifier.
            payload: Analysis payload.

        Returns:
            Persisted job analysis ORM object.
        """

        requirements = [
            JobRequirementModel(
                text=item.text,
                normalized_text=item.normalized_text,
                requirement_type=item.requirement_type,
                is_must_have=item.is_must_have,
                priority_score=item.priority_score,
                sort_order=index,
                source=item.source,
            )
            for index, item in enumerate(payload.requirements)
        ]

        analysis = JobAnalysisModel(
            job_post_id=job_post_id,
            normalized_title=payload.normalized_title,
            detected_language=payload.detected_language,
            summary=payload.summary,
            requirements=requirements,
        )
        self._session.add(analysis)
        self._session.flush()
        return analysis

    def get(self, analysis_id: str) -> JobAnalysisModel | None:
        """Fetch a job analysis by identifier.

        Args:
            analysis_id: Analysis identifier.

        Returns:
            Analysis model with requirements when found, otherwise None.
        """

        stmt = (
            select(JobAnalysisModel)
            .where(JobAnalysisModel.id == analysis_id)
            .options(selectinload(JobAnalysisModel.requirements))
        )
        return self._session.scalar(stmt)

    def get_latest_for_job_post(self, job_post_id: str) -> JobAnalysisModel | None:
        """Fetch the latest analysis for a specific job post.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Latest analysis model with requirements when found.
        """

        stmt = (
            select(JobAnalysisModel)
            .where(JobAnalysisModel.job_post_id == job_post_id)
            .options(selectinload(JobAnalysisModel.requirements))
            .order_by(JobAnalysisModel.created_at.desc())
            .limit(1)
        )
        return self._session.scalar(stmt)

    def get_latest_created_at(self, job_post_id: str) -> datetime | None:
        """Return the latest analysis creation timestamp for a job.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Latest timestamp when analyses exist.
        """

        latest = self.get_latest_for_job_post(job_post_id)
        if latest is None:
            return None
        return latest.created_at
