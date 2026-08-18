from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StaffingOutcome(StrEnum):
    USE_EXISTING_PROFILE = "USE_EXISTING_PROFILE"
    ADD_SKILL_TO_EXISTING_PROFILE = "ADD_SKILL_TO_EXISTING_PROFILE"
    ADD_RUNBOOK = "ADD_RUNBOOK"
    ADD_TASK_TEMPLATE = "ADD_TASK_TEMPLATE"
    CREATE_ROUTINE_PROFILE = "CREATE_ROUTINE_PROFILE"
    CREATE_PROFESSIONAL_PROFILE = "CREATE_PROFESSIONAL_PROFILE"
    DEFER = "DEFER"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ProfileCapability:
    profile_id: str
    lifecycle: str
    capabilities: frozenset[str]
    authorized_skills: frozenset[str]


@dataclass(frozen=True)
class StaffingNeed:
    capability: str
    required_skills: frozenset[str] = frozenset()
    admitted_registry_skills: frozenset[str] = frozenset()
    procedural: bool = False
    task_shape_only: bool = False
    recurring: bool = False
    distinct_identity_authority: bool = False
    requester_is_worker: bool = False
    authority_expansion: bool = False


@dataclass(frozen=True)
class StaffingDecision:
    outcome: StaffingOutcome
    profile_id: str | None = None
    missing_skills: tuple[str, ...] = ()


class StaffingEngine:
    """Resolve workforce gaps without mutating or self-expanding the workforce."""

    def __init__(self, profiles: tuple[ProfileCapability, ...]) -> None:
        self._profiles = profiles

    def resolve(self, need: StaffingNeed) -> StaffingDecision:
        if not need.capability.strip():
            return StaffingDecision(StaffingOutcome.REJECT)
        if need.requester_is_worker and need.authority_expansion:
            return StaffingDecision(StaffingOutcome.REJECT)

        candidates = sorted(
            (
                profile
                for profile in self._profiles
                if profile.lifecycle == "ACTIVE" and need.capability in profile.capabilities
            ),
            key=lambda profile: profile.profile_id,
        )
        for profile in candidates:
            missing = tuple(sorted(need.required_skills - profile.authorized_skills))
            if not missing:
                return StaffingDecision(
                    StaffingOutcome.USE_EXISTING_PROFILE,
                    profile_id=profile.profile_id,
                )
            if set(missing).issubset(need.admitted_registry_skills):
                return StaffingDecision(
                    StaffingOutcome.ADD_SKILL_TO_EXISTING_PROFILE,
                    profile_id=profile.profile_id,
                    missing_skills=missing,
                )

        if need.procedural:
            return StaffingDecision(StaffingOutcome.ADD_RUNBOOK)
        if need.task_shape_only:
            return StaffingDecision(StaffingOutcome.ADD_TASK_TEMPLATE)
        if need.recurring and need.distinct_identity_authority:
            return StaffingDecision(StaffingOutcome.CREATE_PROFESSIONAL_PROFILE)
        if need.recurring:
            return StaffingDecision(StaffingOutcome.CREATE_ROUTINE_PROFILE)
        return StaffingDecision(StaffingOutcome.DEFER)
