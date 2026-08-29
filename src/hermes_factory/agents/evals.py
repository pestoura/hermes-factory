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
    "canonical_inference_identity",
    "independent_review",
)
_KNOWN_DIMENSIONS = frozenset((*_BASE_DIMENSIONS, "native_cron_projection"))


class ProfileEvalHarness:
    def evaluate(
        self,
        profile_id: str,
        profile_digest: str,
        evidence: tuple[ProfileEvalEvidence, ...],
        *,
        scheduled_duties: bool,
    ) -> ProfileEvalRecord:
        if not profile_id.strip():
            raise ProfileAdmissionError("Profile identity is required")
        if not profile_digest.strip():
            raise ProfileAdmissionError("Profile digest is required")

        observed: dict[str, ProfileEvalState] = {}
        for record in evidence:
            if record.profile_id != profile_id:
                raise ProfileAdmissionError("evidence belongs to another Profile")
            if record.profile_digest != profile_digest:
                raise ProfileAdmissionError("evidence Profile digest does not match candidate")
            if record.dimension not in _KNOWN_DIMENSIONS:
                raise ProfileAdmissionError(
                    f"unknown Profile evaluation dimension: {record.dimension}"
                )
            if record.dimension in observed:
                raise ProfileAdmissionError(
                    f"duplicate Profile evaluation dimension: {record.dimension}"
                )
            if not record.evidence_ref.strip() or not record.evaluator.strip():
                raise ProfileAdmissionError("Profile evaluation evidence provenance is required")
            if record.dimension == "independent_review" and record.evaluator == profile_id:
                raise ProfileAdmissionError("independent review cannot be self-review")
            observed[record.dimension] = record.state

        required = list(_BASE_DIMENSIONS)
        if scheduled_duties:
            required.append("native_cron_projection")

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
