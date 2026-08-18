from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProfileAdmissionError(ValueError):
    pass


class ProfileEvalState(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ProfileEvalEvidence:
    profile_id: str
    profile_digest: str
    dimension: str
    state: ProfileEvalState
    evidence_ref: str
    evaluator: str


@dataclass(frozen=True)
class ProfileEvalRecord:
    profile_id: str
    profile_digest: str
    required_states: dict[str, ProfileEvalState]
    eligible_for_activation: bool


_BASE_DIMENSIONS = (
    "routing_correctness",
    "refusal_authority_boundary",
    "tool_policy_projection",
    "skill_allowlist",
    "separation_of_duties",
    "handoff_evidence_quality",
    "escalation_correctness",
    "no_internal_mcp_dependency",
    "independent_review",
)


class ProfileEvalHarness:
    def evaluate(
        self,
        profile_id: str,
        profile_digest: str,
        evidence: tuple[ProfileEvalEvidence, ...],
        *,
        scheduled_duties: bool,
    ) -> ProfileEvalRecord:
        required = list(_BASE_DIMENSIONS)
        if scheduled_duties:
            required.append("native_cron_projection")

        observed = {record.dimension: record.state for record in evidence}
        required_states = {
            dimension: observed.get(dimension, ProfileEvalState.NOT_RUN)
            for dimension in required
        }
        return ProfileEvalRecord(
            profile_id=profile_id,
            profile_digest=profile_digest,
            required_states=required_states,
            eligible_for_activation=all(
                state is ProfileEvalState.PASS for state in required_states.values()
            ),
        )
