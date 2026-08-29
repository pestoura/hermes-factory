from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hermes_factory.runtime.admission import AdmissionEvidenceState

RUNTIME_ACCEPTANCE_SCENARIOS = (
    "project_onboarding_compile",
    "dependency_driven_profile_handoff",
    "independent_code_security_integration_uat",
    "fail_finding_bounded_rework_rerun",
    "stale_sha_invalidates_evidence",
    "hitl_valid_decision_resumes_affected_work",
    "expired_stale_replayed_hitl_cannot_unlock",
    "unrelated_wps_continue_during_waiting_hitl",
    "time_driven_job_uses_native_hermes_cron_only",
    "runtime_observation_read_only_distinct_from_deployment",
    "acceptance_refuses_not_run_unknown_stale",
    "dashboard_reflects_canonical_truth",
    "external_northbound_control_without_internal_ipc",
    "all_17_profile_runtime_projections_validate",
    "all_required_factory_skills_have_explicit_eval_state",
    "superseded_generation_retirement_preserves_history",
    "all_factory_workers_use_canonical_inference_identity",
)


@dataclass(frozen=True)
class RuntimeAcceptanceEvidence:
    scenario: str
    candidate_sha: str
    state: AdmissionEvidenceState
    evidence_ref: str


@dataclass(frozen=True)
class RuntimeAcceptanceAssessment:
    candidate_sha: str
    scenario_states: dict[str, AdmissionEvidenceState]
    blockers: tuple[str, ...]
    accepted_runtime: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/runtime-acceptance/v1",
            "candidate_sha": self.candidate_sha,
            "scenario_states": {
                scenario: self.scenario_states[scenario].value
                for scenario in RUNTIME_ACCEPTANCE_SCENARIOS
            },
            "blockers": list(self.blockers),
            "accepted_runtime": self.accepted_runtime,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_manifest(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class RuntimeAcceptanceMatrix:
    def __init__(self, *, candidate_sha: str) -> None:
        if len(candidate_sha) != 40 or not candidate_sha.strip():
            raise ValueError("runtime acceptance candidate SHA must be a 40-character commit SHA")
        self.candidate_sha = candidate_sha
        self.scenarios = RUNTIME_ACCEPTANCE_SCENARIOS

    def assess(
        self,
        evidence: tuple[RuntimeAcceptanceEvidence, ...],
    ) -> RuntimeAcceptanceAssessment:
        observed: dict[str, AdmissionEvidenceState] = {}
        for record in evidence:
            if record.candidate_sha != self.candidate_sha:
                raise ValueError("runtime acceptance evidence candidate SHA does not match")
            if record.scenario not in self.scenarios:
                raise ValueError(f"unknown runtime acceptance scenario {record.scenario}")
            if record.scenario in observed:
                raise ValueError(
                    f"duplicate runtime acceptance evidence for {record.scenario}"
                )
            if not record.evidence_ref.strip():
                raise ValueError("runtime acceptance evidence requires provenance")
            observed[record.scenario] = record.state

        states = {
            scenario: observed.get(scenario, AdmissionEvidenceState.NOT_RUN)
            for scenario in self.scenarios
        }
        blockers = tuple(
            f"Scenario {scenario}={state.value}"
            for scenario, state in states.items()
            if state is not AdmissionEvidenceState.PASS
        )
        return RuntimeAcceptanceAssessment(
            candidate_sha=self.candidate_sha,
            scenario_states=states,
            blockers=blockers,
            accepted_runtime=not blockers,
        )
