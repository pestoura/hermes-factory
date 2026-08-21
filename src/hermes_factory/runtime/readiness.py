from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hermes_factory.runtime.admission import (
    AdmissionEvidenceState,
    RuntimeComponent,
)


@dataclass(frozen=True)
class RuntimeReadinessAssessment:
    profile_states: dict[str, AdmissionEvidenceState]
    skill_states: dict[str, AdmissionEvidenceState]
    component_states: dict[RuntimeComponent, AdmissionEvidenceState]
    blockers: tuple[str, ...]
    ready: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/runtime-readiness/v1",
            "profile_states": {
                identity: state.value
                for identity, state in sorted(self.profile_states.items())
            },
            "skill_states": {
                identity: state.value
                for identity, state in sorted(self.skill_states.items())
            },
            "component_states": {
                component.value: self.component_states[component].value
                for component in RuntimeComponent
                if component in self.component_states
            },
            "blockers": list(self.blockers),
            "ready": self.ready,
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


class RuntimeReadinessAssessor:
    def assess(
        self,
        *,
        required_profile_ids: Sequence[str],
        required_skill_ids: Sequence[str],
        profile_eval_states: Mapping[str, AdmissionEvidenceState],
        skill_eval_states: Mapping[str, AdmissionEvidenceState],
        component_states: Mapping[RuntimeComponent, AdmissionEvidenceState] | None = None,
    ) -> RuntimeReadinessAssessment:
        required_profiles = tuple(sorted(required_profile_ids))
        required_skills = tuple(sorted(required_skill_ids))
        required_profile_set = frozenset(required_profiles)
        required_skill_set = frozenset(required_skills)

        profiles = {
            identity: profile_eval_states.get(identity, AdmissionEvidenceState.ABSENT)
            for identity in required_profiles
        }
        skills = {
            identity: skill_eval_states.get(identity, AdmissionEvidenceState.ABSENT)
            for identity in required_skills
        }
        observed_components = component_states or {}
        components = {
            component: observed_components.get(component, AdmissionEvidenceState.ABSENT)
            for component in RuntimeComponent
        }

        profile_blockers = [
            f"Profile {identity}={state.value}"
            for identity, state in profiles.items()
            if state is not AdmissionEvidenceState.PASS
        ]
        skill_blockers = [
            f"Skill {identity}={state.value}"
            for identity, state in skills.items()
            if state is not AdmissionEvidenceState.PASS
        ]
        component_blockers = [
            f"Component {component.value}={state.value}"
            for component, state in components.items()
            if state is not AdmissionEvidenceState.PASS
        ]
        unexpected_profile_blockers = [
            f"Unexpected Profile evidence {identity}={profile_eval_states[identity].value}"
            for identity in sorted(set(profile_eval_states) - required_profile_set)
        ]
        unexpected_skill_blockers = [
            f"Unexpected Skill evidence {identity}={skill_eval_states[identity].value}"
            for identity in sorted(set(skill_eval_states) - required_skill_set)
        ]

        blockers = tuple(
            profile_blockers
            + skill_blockers
            + component_blockers
            + unexpected_profile_blockers
            + unexpected_skill_blockers
        )
        return RuntimeReadinessAssessment(
            profile_states=profiles,
            skill_states=skills,
            component_states=components,
            blockers=blockers,
            ready=not blockers,
        )
