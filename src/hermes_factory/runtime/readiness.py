from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hermes_factory.runtime.admission import AdmissionEvidenceState


@dataclass(frozen=True)
class RuntimeReadinessAssessment:
    profile_states: dict[str, AdmissionEvidenceState]
    skill_states: dict[str, AdmissionEvidenceState]
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
    ) -> RuntimeReadinessAssessment:
        profile_states = {
            identity: profile_eval_states.get(identity, AdmissionEvidenceState.ABSENT)
            for identity in sorted(required_profile_ids)
        }
        skill_states = {
            identity: skill_eval_states.get(identity, AdmissionEvidenceState.ABSENT)
            for identity in sorted(required_skill_ids)
        }

        blockers = tuple(
            [
                f"Profile {identity}={state.value}"
                for identity, state in profile_states.items()
                if state is not AdmissionEvidenceState.PASS
            ]
            + [
                f"Skill {identity}={state.value}"
                for identity, state in skill_states.items()
                if state is not AdmissionEvidenceState.PASS
            ]
        )
        return RuntimeReadinessAssessment(
            profile_states=profile_states,
            skill_states=skill_states,
            blockers=blockers,
            ready=not blockers,
        )
