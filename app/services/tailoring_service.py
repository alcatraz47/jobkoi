"""Service for deterministic tailoring plan and snapshot orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.job import JobAnalysisModel
from app.db.models.profile import MasterProfileVersionModel
from app.db.models.tailoring import ProfileSnapshotModel, TailoringPlanModel
from app.db.repositories.job_repository import JobAnalysisRepository
from app.db.repositories.profile_repository import ProfileRepository
from app.db.repositories.tailoring_repository import (
    ProfileSnapshotCreatePayload,
    SnapshotEducationPayload,
    SnapshotExperiencePayload,
    SnapshotSkillPayload,
    TailoringPlanCreatePayload,
    TailoringPlanItemPayload,
    TailoringRepository,
)
from app.domain.tailoring_builders import build_profile_snapshot, build_tailoring_plan
from app.domain.tailoring_guards import InventedClaimError, validate_rewrites_against_selected_facts
from app.domain.tailoring_types import (
    JobAnalysisData,
    JobRequirementData,
    ProfileEducationFact,
    ProfileExperienceFact,
    ProfileSkillFact,
    ProfileSnapshotDraft,
    ProfileVersionData,
    TailoringPlanDraft,
    TailoringPlanFactDraft,
)
from app.llm.tailoring_rewrite_adapter import TailoringRewriteLlmAdapter
from app.schemas.tailoring import (
    SnapshotEducationResponse,
    SnapshotExperienceResponse,
    SnapshotSkillResponse,
    TailoredSnapshotCreateRequest,
    TailoredSnapshotResponse,
    TailoringPlanCreateRequest,
    TailoringPlanFactResponse,
    TailoringPlanResponse,
)


class TailoringDependencyNotFoundError(Exception):
    """Raised when required source entities for tailoring are missing."""


class TailoringPlanNotFoundError(Exception):
    """Raised when a tailoring plan cannot be found."""


class TailoringSnapshotNotFoundError(Exception):
    """Raised when a tailored snapshot cannot be found."""


class TailoringValidationError(Exception):
    """Raised when tailoring guard validation fails."""


class TailoringService:
    """Service coordinating deterministic tailoring logic and persistence."""

    def __init__(
        self,
        session: Session,
        rewrite_adapter: TailoringRewriteLlmAdapter | None = None,
    ) -> None:
        """Initialize service with repository dependencies.

        Args:
            session: Active database session.
            rewrite_adapter: Optional LLM rewrite adapter.
        """

        self._session = session
        self._profile_repository = ProfileRepository(session)
        self._analysis_repository = JobAnalysisRepository(session)
        self._tailoring_repository = TailoringRepository(session)
        self._rewrite_adapter = rewrite_adapter

    def create_tailoring_plan(self, request: TailoringPlanCreateRequest) -> TailoringPlanResponse:
        """Create a deterministic tailoring plan.

        Args:
            request: Tailoring plan creation payload.

        Returns:
            Persisted tailoring plan response.

        Raises:
            TailoringDependencyNotFoundError: If profile version or job analysis is missing.
        """

        profile_version = self._resolve_profile_version(request.profile_version_id)
        analysis = self._analysis_repository.get(request.job_analysis_id)
        if analysis is None:
            raise TailoringDependencyNotFoundError("Job analysis not found.")

        profile_data = self._to_profile_version_data(profile_version)
        analysis_data = self._to_job_analysis_data(analysis)

        draft = build_tailoring_plan(
            profile=profile_data,
            analysis=analysis_data,
            target_language=request.target_language,
            max_experiences=request.max_experiences,
            max_skills=request.max_skills,
            max_educations=request.max_educations,
        )

        payload = TailoringPlanCreatePayload(
            job_analysis_id=draft.job_analysis_id,
            profile_version_id=draft.profile_version_id,
            target_language=draft.target_language,
            summary=draft.summary,
            items=[self._to_plan_item_payload(item) for item in draft.facts],
        )
        plan = self._tailoring_repository.create_plan(payload)
        self._session.commit()
        return self._to_plan_response(plan)

    def get_tailoring_plan(self, plan_id: str) -> TailoringPlanResponse:
        """Get one tailoring plan.

        Args:
            plan_id: Tailoring plan identifier.

        Returns:
            Tailoring plan response.

        Raises:
            TailoringPlanNotFoundError: If plan does not exist.
        """

        plan = self._tailoring_repository.get_plan(plan_id)
        if plan is None:
            raise TailoringPlanNotFoundError("Tailoring plan not found.")
        return self._to_plan_response(plan)

    def create_snapshot(self, request: TailoredSnapshotCreateRequest) -> TailoredSnapshotResponse:
        """Create an immutable tailored profile snapshot.

        Args:
            request: Snapshot creation payload.

        Returns:
            Persisted tailored snapshot response.

        Raises:
            TailoringPlanNotFoundError: If tailoring plan does not exist.
            TailoringDependencyNotFoundError: If source profile version is missing.
            TailoringValidationError: If factual guards reject rewrite claims.
        """

        plan, profile_data, plan_draft = self._load_snapshot_dependencies(request.tailoring_plan_id)
        rewrites = self._build_rewrite_map(plan=plan, request=request)
        snapshot_draft = build_profile_snapshot(profile=profile_data, plan=plan_draft, rewrites=rewrites)
        payload = self._to_snapshot_payload(plan_id=plan.id, draft=snapshot_draft)

        snapshot = self._tailoring_repository.create_snapshot(payload)
        self._session.commit()
        return self._to_snapshot_response(snapshot)

    def _load_snapshot_dependencies(
        self,
        tailoring_plan_id: str,
    ) -> tuple[TailoringPlanModel, ProfileVersionData, TailoringPlanDraft]:
        """Load and map dependencies required for snapshot creation.

        Args:
            tailoring_plan_id: Tailoring plan identifier.

        Returns:
            Tuple of plan model, mapped profile data, and mapped plan draft.

        Raises:
            TailoringPlanNotFoundError: If plan does not exist.
            TailoringDependencyNotFoundError: If profile version is missing.
        """

        plan = self._tailoring_repository.get_plan(tailoring_plan_id)
        if plan is None:
            raise TailoringPlanNotFoundError("Tailoring plan not found.")

        profile_version = self._profile_repository.get_profile_version_by_id(plan.profile_version_id)
        if profile_version is None:
            raise TailoringDependencyNotFoundError("Profile version not found.")

        return plan, self._to_profile_version_data(profile_version), self._to_plan_draft(plan)

    def _build_rewrite_map(
        self,
        *,
        plan: TailoringPlanModel,
        request: TailoredSnapshotCreateRequest,
    ) -> dict[str, str]:
        """Build validated rewrite map for snapshot generation.

        Args:
            plan: Source tailoring plan.
            request: Snapshot creation request.

        Returns:
            Final rewrite mapping with manual rewrites overriding LLM rewrites.

        Raises:
            TailoringValidationError: If rewrite validation fails.
        """

        selected_fact_texts = self._extract_selected_fact_texts(plan)
        manual_rewrites = {item.fact_key: item.rewritten_text for item in request.rewrites}
        llm_rewrites = self._get_optional_llm_rewrites(
            use_llm=request.use_llm_rewrite,
            selected_fact_texts=selected_fact_texts,
            target_language=plan.target_language,
        )
        rewrites = {**llm_rewrites, **manual_rewrites}
        self._validate_rewrites(selected_fact_texts=selected_fact_texts, rewrites=rewrites)
        return rewrites

    @staticmethod
    def _extract_selected_fact_texts(plan: TailoringPlanModel) -> dict[str, str]:
        """Extract selected fact text mapping from a tailoring plan.

        Args:
            plan: Source tailoring plan.

        Returns:
            Mapping of selected fact key to source text.
        """

        return {item.fact_key: item.source_text for item in plan.items if item.is_selected}

    @staticmethod
    def _validate_rewrites(*, selected_fact_texts: dict[str, str], rewrites: dict[str, str]) -> None:
        """Validate rewrite claims against selected source facts.

        Args:
            selected_fact_texts: Selected source fact map.
            rewrites: Candidate rewrite map.

        Raises:
            TailoringValidationError: If validation rejects one or more claims.
        """

        try:
            validate_rewrites_against_selected_facts(
                selected_fact_texts=selected_fact_texts,
                rewrites=rewrites,
            )
        except InventedClaimError as exc:
            raise TailoringValidationError(str(exc)) from exc

    @staticmethod
    def _to_snapshot_payload(*, plan_id: str, draft: ProfileSnapshotDraft) -> ProfileSnapshotCreatePayload:
        """Map snapshot draft into repository payload.

        Args:
            plan_id: Tailoring plan identifier.
            draft: Built snapshot draft.

        Returns:
            Repository payload for snapshot persistence.
        """

        return ProfileSnapshotCreatePayload(
            tailoring_plan_id=plan_id,
            profile_version_id=draft.profile_version_id,
            target_language=draft.target_language,
            full_name=draft.full_name,
            email=draft.email,
            phone=draft.phone,
            location=draft.location,
            headline=draft.headline,
            summary=draft.summary,
            experiences=[
                SnapshotExperiencePayload(
                    source_experience_id=item.source_experience_id,
                    company=item.company,
                    title=item.title,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    description=item.description,
                    relevance_score=item.relevance_score,
                )
                for item in draft.experiences
            ],
            educations=[
                SnapshotEducationPayload(
                    source_education_id=item.source_education_id,
                    institution=item.institution,
                    degree=item.degree,
                    field_of_study=item.field_of_study,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    relevance_score=item.relevance_score,
                )
                for item in draft.educations
            ],
            skills=[
                SnapshotSkillPayload(
                    source_skill_id=item.source_skill_id,
                    skill_name=item.skill_name,
                    level=item.level,
                    category=item.category,
                    relevance_score=item.relevance_score,
                )
                for item in draft.skills
            ],
        )

    def get_snapshot(self, snapshot_id: str) -> TailoredSnapshotResponse:
        """Get one tailored profile snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Returns:
            Tailored snapshot response.

        Raises:
            TailoringSnapshotNotFoundError: If snapshot does not exist.
        """

        snapshot = self._tailoring_repository.get_snapshot(snapshot_id)
        if snapshot is None:
            raise TailoringSnapshotNotFoundError("Tailored snapshot not found.")
        return self._to_snapshot_response(snapshot)

    def _resolve_profile_version(self, explicit_version_id: str | None) -> MasterProfileVersionModel:
        """Resolve profile version for plan generation.

        Args:
            explicit_version_id: Optional explicit profile version identifier.

        Returns:
            Resolved master profile version model.

        Raises:
            TailoringDependencyNotFoundError: If profile or requested version is missing.
        """

        if explicit_version_id is not None:
            explicit_version = self._profile_repository.get_profile_version_by_id(explicit_version_id)
            if explicit_version is None:
                raise TailoringDependencyNotFoundError("Profile version not found.")
            return explicit_version

        profile = self._profile_repository.get_profile()
        if profile is None or profile.active_version_id is None:
            raise TailoringDependencyNotFoundError("Active master profile version not found.")

        active_version = self._profile_repository.get_profile_version_by_id(profile.active_version_id)
        if active_version is None:
            raise TailoringDependencyNotFoundError("Active master profile version not found.")
        return active_version

    def _get_optional_llm_rewrites(
        self,
        *,
        use_llm: bool,
        selected_fact_texts: dict[str, str],
        target_language: str,
    ) -> dict[str, str]:
        """Return optional LLM rewrite mapping.

        Args:
            use_llm: LLM rewrite toggle.
            selected_fact_texts: Selected source fact map.
            target_language: Target language code.

        Returns:
            Rewrites returned by LLM adapter or an empty mapping.
        """

        if not use_llm or self._rewrite_adapter is None:
            return {}
        return self._rewrite_adapter.rewrite_selected_facts(
            selected_facts=selected_fact_texts,
            target_language=target_language,
        )

    @staticmethod
    def _to_profile_version_data(profile: MasterProfileVersionModel) -> ProfileVersionData:
        """Map profile version ORM model to domain profile data.

        Args:
            profile: Master profile version ORM model.

        Returns:
            Domain profile version value object.
        """

        experiences = [
            ProfileExperienceFact(
                id=item.id,
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
            )
            for item in profile.experiences
        ]
        educations = [
            ProfileEducationFact(
                id=item.id,
                institution=item.institution,
                degree=item.degree,
                field_of_study=item.field_of_study,
                start_date=item.start_date,
                end_date=item.end_date,
            )
            for item in profile.educations
        ]
        skills = [
            ProfileSkillFact(
                id=item.id,
                skill_name=item.skill_name,
                level=item.level,
                category=item.category,
            )
            for item in profile.skills
        ]

        return ProfileVersionData(
            id=profile.id,
            full_name=profile.full_name,
            email=profile.email,
            phone=profile.phone,
            location=profile.location,
            headline=profile.headline,
            summary=profile.summary,
            experiences=experiences,
            educations=educations,
            skills=skills,
        )

    @staticmethod
    def _to_job_analysis_data(analysis: JobAnalysisModel) -> JobAnalysisData:
        """Map analysis ORM model to domain analysis data.

        Args:
            analysis: Job analysis ORM model.

        Returns:
            Domain analysis value object.
        """

        requirements = [
            JobRequirementData(
                id=item.id,
                text=item.text,
                requirement_type=item.requirement_type,
                is_must_have=item.is_must_have,
                priority_score=item.priority_score,
            )
            for item in analysis.requirements
        ]
        return JobAnalysisData(
            id=analysis.id,
            detected_language=analysis.detected_language,
            requirements=requirements,
        )

    @staticmethod
    def _to_plan_item_payload(item: TailoringPlanFactDraft) -> TailoringPlanItemPayload:
        """Map domain plan fact to repository payload.

        Args:
            item: Domain tailoring plan fact.

        Returns:
            Repository payload.
        """

        return TailoringPlanItemPayload(
            fact_key=item.fact_key,
            fact_type=item.fact_type,
            source_entity_id=item.source_entity_id,
            source_text=item.text,
            relevance_score=item.relevance_score,
            is_selected=item.is_selected,
            selection_reason=item.selection_reason,
        )

    @staticmethod
    def _to_plan_draft(plan: TailoringPlanModel) -> TailoringPlanDraft:
        """Map tailoring plan ORM model to domain draft object.

        Args:
            plan: Tailoring plan ORM model.

        Returns:
            Domain tailoring plan draft.
        """

        facts = [
            TailoringPlanFactDraft(
                fact_key=item.fact_key,
                fact_type=item.fact_type,
                source_entity_id=item.source_entity_id,
                text=item.source_text,
                relevance_score=item.relevance_score,
                is_selected=item.is_selected,
                selection_reason=item.selection_reason,
            )
            for item in plan.items
        ]

        return TailoringPlanDraft(
            profile_version_id=plan.profile_version_id,
            job_analysis_id=plan.job_analysis_id,
            target_language=plan.target_language,
            summary=plan.summary,
            facts=facts,
        )

    @staticmethod
    def _to_plan_response(plan: TailoringPlanModel) -> TailoringPlanResponse:
        """Map tailoring plan ORM model to API response.

        Args:
            plan: Tailoring plan ORM model.

        Returns:
            Tailoring plan response payload.
        """

        items = [
            TailoringPlanFactResponse(
                fact_key=item.fact_key,
                fact_type=item.fact_type,
                source_entity_id=item.source_entity_id,
                text=item.source_text,
                relevance_score=item.relevance_score,
                is_selected=item.is_selected,
                selection_reason=item.selection_reason,
            )
            for item in plan.items
        ]

        return TailoringPlanResponse(
            id=plan.id,
            job_analysis_id=plan.job_analysis_id,
            profile_version_id=plan.profile_version_id,
            target_language=plan.target_language,
            summary=plan.summary,
            created_at=plan.created_at,
            selected_item_count=sum(1 for item in items if item.is_selected),
            items=items,
        )

    @staticmethod
    def _to_snapshot_response(snapshot: ProfileSnapshotModel) -> TailoredSnapshotResponse:
        """Map profile snapshot ORM model to API response.

        Args:
            snapshot: Profile snapshot ORM model.

        Returns:
            Tailored snapshot response payload.
        """

        experiences = [
            SnapshotExperienceResponse(
                id=item.id,
                source_experience_id=item.source_experience_id,
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
                relevance_score=item.relevance_score,
                sort_order=item.sort_order,
            )
            for item in snapshot.experiences
        ]
        educations = [
            SnapshotEducationResponse(
                id=item.id,
                source_education_id=item.source_education_id,
                institution=item.institution,
                degree=item.degree,
                field_of_study=item.field_of_study,
                start_date=item.start_date,
                end_date=item.end_date,
                relevance_score=item.relevance_score,
                sort_order=item.sort_order,
            )
            for item in snapshot.educations
        ]
        skills = [
            SnapshotSkillResponse(
                id=item.id,
                source_skill_id=item.source_skill_id,
                skill_name=item.skill_name,
                level=item.level,
                category=item.category,
                relevance_score=item.relevance_score,
                sort_order=item.sort_order,
            )
            for item in snapshot.skills
        ]

        return TailoredSnapshotResponse(
            id=snapshot.id,
            tailoring_plan_id=snapshot.tailoring_plan_id,
            profile_version_id=snapshot.profile_version_id,
            target_language=snapshot.target_language,
            full_name=snapshot.full_name,
            email=snapshot.email,
            phone=snapshot.phone,
            location=snapshot.location,
            headline=snapshot.headline,
            summary=snapshot.summary,
            created_at=snapshot.created_at,
            experiences=experiences,
            educations=educations,
            skills=skills,
        )
