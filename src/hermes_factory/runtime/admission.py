from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from hermes_factory.gates.exact_sha import ExactSHAState, evaluate_exact_sha


class RuntimeAdmissionError(ValueError):
    pass


class AdmissionEvidenceState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    ABSENT = "ABSENT"


class RuntimeComponent(StrEnum):
    FACTORY_PACKAGE = "FACTORY_PACKAGE"
    PROFILE_DISTRIBUTIONS = "PROFILE_DISTRIBUTIONS"
    FACTORY_SKILLS = "FACTORY_SKILLS"
    KANBAN_HIGH_ASSURANCE_POLICY = "KANBAN_HIGH_ASSURANCE_POLICY"
    NATIVE_PROFILE_CRON = "NATIVE_PROFILE_CRON"
    DASHBOARD_PLUGIN = "DASHBOARD_PLUGIN"
    GATEWAY_HITL_ADAPTER = "GATEWAY_HITL_ADAPTER"
    NORTHBOUND_CONTROL_INTEGRATION = "NORTHBOUND_CONTROL_INTEGRATION"


_COMPONENTS = (
    RuntimeComponent.FACTORY_PACKAGE,
    RuntimeComponent.PROFILE_DISTRIBUTIONS,
    RuntimeComponent.FACTORY_SKILLS,
    RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
    RuntimeComponent.NATIVE_PROFILE_CRON,
    RuntimeComponent.DASHBOARD_PLUGIN,
    RuntimeComponent.GATEWAY_HITL_ADAPTER,
    RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION,
)


@dataclass(frozen=True)
class RuntimeInstallPlan:
    hermes_sha: str
    components: tuple[RuntimeComponent, ...]
    profiles_to_admit: tuple[str, ...]
    skills_to_admit: tuple[str, ...]
    runtime_state: AdmissionEvidenceState
    execute: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/runtime-install-plan/v1",
            "hermes_sha": self.hermes_sha,
            "components": [component.value for component in self.components],
            "profiles_to_admit": list(self.profiles_to_admit),
            "skills_to_admit": list(self.skills_to_admit),
            "runtime_state": self.runtime_state.value,
            "execute": self.execute,
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


def _require_identities(
    evidence_type: str,
    states: Mapping[str, AdmissionEvidenceState],
) -> None:
    if any(not identity.strip() for identity in states):
        raise RuntimeAdmissionError(f"{evidence_type} identity is required")


def _require_pass(
    evidence_type: str,
    states: Mapping[str, AdmissionEvidenceState],
) -> None:
    non_pass = tuple(
        sorted(
            (identity, state)
            for identity, state in states.items()
            if state is not AdmissionEvidenceState.PASS
        )
    )
    if not non_pass:
        return
    details = ", ".join(f"{identity}={state.value}" for identity, state in non_pass)
    raise RuntimeAdmissionError(f"{evidence_type} evaluation must PASS: {details}")


class RuntimeAdmissionPlanner:
    def build(
        self,
        *,
        accepted_hermes_sha: str,
        observed_hermes_sha: str,
        profile_eval_states: Mapping[str, AdmissionEvidenceState],
        skill_eval_states: Mapping[str, AdmissionEvidenceState],
    ) -> RuntimeInstallPlan:
        sha_state = evaluate_exact_sha(accepted_hermes_sha, (observed_hermes_sha,))
        if sha_state is not ExactSHAState.SHA_MATCH:
            raise RuntimeAdmissionError("exact Hermes SHA match is required for runtime admission")

        _require_identities("Profile", profile_eval_states)
        _require_identities("Skill", skill_eval_states)
        _require_pass("Profile", profile_eval_states)
        _require_pass("Skill", skill_eval_states)

        return RuntimeInstallPlan(
            hermes_sha=accepted_hermes_sha,
            components=_COMPONENTS,
            profiles_to_admit=tuple(sorted(profile_eval_states)),
            skills_to_admit=tuple(sorted(skill_eval_states)),
            runtime_state=AdmissionEvidenceState.NOT_RUN,
            execute=False,
        )
