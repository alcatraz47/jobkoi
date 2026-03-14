"""Service for deterministic and optional LLM-assisted job analysis."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.job import JobAnalysisModel, JobRequirementModel
from app.db.repositories.job_repository import (
    JobAnalysisCreatePayload,
    JobAnalysisRepository,
    JobPostRepository,
    JobRequirementPayload,
)
from app.domain.job_analysis import JobAnalysisDraft, RequirementDraft, build_structured_job_analysis
from app.domain.job_text import normalize_text
from app.llm.job_analysis_adapter import JobAnalysisLlmAdapter, LlmRequirementSuggestion
from app.schemas.job import JobAnalysisCreateRequest, JobAnalysisResponse, JobRequirementResponse
from app.services.job_post_service import JobPostNotFoundError


class JobAnalysisNotFoundError(Exception):
    """Raised when job analysis data cannot be found."""


class JobAnalysisService:
    """Service coordinating deterministic structured job analysis creation."""

    def __init__(self, session: Session, llm_adapter: JobAnalysisLlmAdapter | None = None) -> None:
        """Initialize service with persistence dependencies.

        Args:
            session: Active database session.
            llm_adapter: Optional adapter for LLM-assisted requirement suggestions.
        """

        self._session = session
        self._job_post_repository = JobPostRepository(session)
        self._analysis_repository = JobAnalysisRepository(session)
        self._llm_adapter = llm_adapter

    def analyze_job_post(
        self,
        *,
        job_post_id: str,
        request: JobAnalysisCreateRequest,
    ) -> JobAnalysisResponse:
        """Analyze a job post and persist structured requirements.

        Args:
            job_post_id: Job post identifier.
            request: Analysis creation request payload.

        Returns:
            Persisted structured analysis response.

        Raises:
            JobPostNotFoundError: If the source job post is missing.
        """

        job_post = self._job_post_repository.get(job_post_id)
        if job_post is None:
            raise JobPostNotFoundError("Job post not found.")

        draft = build_structured_job_analysis(
            title=job_post.title,
            description=job_post.normalized_description,
            detected_language=job_post.detected_language,
        )
        requirements = list(draft.requirements)

        if request.use_llm and self._llm_adapter is not None:
            requirements = self._merge_llm_suggestions(
                base=requirements,
                suggestions=self._llm_adapter.extract_requirements(
                    title=job_post.title,
                    description=job_post.normalized_description,
                    detected_language=job_post.detected_language,
                ),
            )

        payload = JobAnalysisCreatePayload(
            normalized_title=draft.normalized_title,
            detected_language=draft.detected_language,
            summary=draft.summary,
            requirements=[self._to_requirement_payload(item) for item in requirements],
        )
        model = self._analysis_repository.create(job_post_id=job_post_id, payload=payload)
        self._session.commit()
        return self._to_analysis_response(model)

    def get_latest_for_job_post(self, job_post_id: str) -> JobAnalysisResponse:
        """Return the latest analysis for a job post.

        Args:
            job_post_id: Job post identifier.

        Returns:
            Latest analysis response.

        Raises:
            JobPostNotFoundError: If job post does not exist.
            JobAnalysisNotFoundError: If no analysis exists for the job post.
        """

        if self._job_post_repository.get(job_post_id) is None:
            raise JobPostNotFoundError("Job post not found.")

        analysis = self._analysis_repository.get_latest_for_job_post(job_post_id)
        if analysis is None:
            raise JobAnalysisNotFoundError("Job analysis not found.")
        return self._to_analysis_response(analysis)

    def get_analysis(self, analysis_id: str) -> JobAnalysisResponse:
        """Fetch one stored analysis by identifier.

        Args:
            analysis_id: Analysis identifier.

        Returns:
            Analysis response payload.

        Raises:
            JobAnalysisNotFoundError: If the analysis does not exist.
        """

        analysis = self._analysis_repository.get(analysis_id)
        if analysis is None:
            raise JobAnalysisNotFoundError("Job analysis not found.")
        return self._to_analysis_response(analysis)

    @staticmethod
    def _to_requirement_payload(requirement: RequirementDraft) -> JobRequirementPayload:
        """Map a requirement draft to repository payload.

        Args:
            requirement: Requirement draft value object.

        Returns:
            Repository payload for requirement persistence.
        """

        return JobRequirementPayload(
            text=requirement.text,
            normalized_text=requirement.normalized_text,
            requirement_type=requirement.requirement_type,
            is_must_have=requirement.is_must_have,
            priority_score=requirement.priority_score,
            source=requirement.source,
        )

    @staticmethod
    def _to_analysis_response(model: JobAnalysisModel) -> JobAnalysisResponse:
        """Map analysis ORM model to API response schema.

        Args:
            model: Persisted analysis ORM model.

        Returns:
            Analysis response payload.
        """

        requirements = [
            JobRequirementResponse(
                id=requirement.id,
                text=requirement.text,
                requirement_type=requirement.requirement_type,
                is_must_have=requirement.is_must_have,
                is_nice_to_have=not requirement.is_must_have,
                priority_score=requirement.priority_score,
                source=requirement.source,
            )
            for requirement in model.requirements
        ]

        return JobAnalysisResponse(
            id=model.id,
            job_post_id=model.job_post_id,
            normalized_title=model.normalized_title,
            detected_language=model.detected_language,
            summary=model.summary,
            created_at=model.created_at,
            requirements=requirements,
        )

    def _merge_llm_suggestions(
        self,
        *,
        base: list[RequirementDraft],
        suggestions: list[LlmRequirementSuggestion],
    ) -> list[RequirementDraft]:
        """Merge deterministic and optional LLM requirements without duplicates.

        Args:
            base: Deterministic requirement list.
            suggestions: LLM-provided requirement suggestions.

        Returns:
            Merged deterministic requirement list ordered by priority and source order.
        """

        existing = {item.normalized_text for item in base}
        merged = list(base)
        source_index = len(base)

        for suggestion in suggestions:
            normalized = normalize_text(suggestion.text).lower()
            if not normalized or normalized in existing:
                continue

            merged.append(
                RequirementDraft(
                    text=normalize_text(suggestion.text),
                    normalized_text=normalized,
                    requirement_type=suggestion.requirement_type,
                    is_must_have=suggestion.is_must_have,
                    priority_score=max(0, min(100, suggestion.priority_score)),
                    source_line_index=source_index,
                    source="llm",
                )
            )
            existing.add(normalized)
            source_index += 1

        return sorted(merged, key=lambda item: (-item.priority_score, item.source_line_index))
