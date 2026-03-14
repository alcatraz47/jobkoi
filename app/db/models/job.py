"""ORM models for job ingestion and structured analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Returns:
        The current timezone-aware UTC timestamp.
    """

    return datetime.now(timezone.utc)


class JobPostModel(Base):
    """Stored job post text submitted by the user.

    Attributes:
        id: Primary identifier.
        title: Raw job title.
        company: Optional company name.
        description_raw: Raw pasted job description.
        normalized_description: Deterministically normalized description text.
        detected_language: Detected language code.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        analyses: Associated analysis runs.
    """

    __tablename__ = "job_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    analyses: Mapped[list[JobAnalysisModel]] = relationship(
        back_populates="job_post",
        cascade="all, delete-orphan",
        order_by="JobAnalysisModel.created_at.desc()",
    )


class JobAnalysisModel(Base):
    """Structured analysis result for one job post."""

    __tablename__ = "job_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False
    )
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_language: Mapped[str] = mapped_column(String(8), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    job_post: Mapped[JobPostModel] = relationship(back_populates="analyses")
    requirements: Mapped[list[JobRequirementModel]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="JobRequirementModel.sort_order",
    )


class JobRequirementModel(Base):
    """Requirement extracted from a job analysis."""

    __tablename__ = "job_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_analyses.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_must_have: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="rule_based")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    analysis: Mapped[JobAnalysisModel] = relationship(back_populates="requirements")
