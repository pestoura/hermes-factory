from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.runtime.admission import AdmissionEvidenceState


@dataclass(frozen=True)
class EvalReadinessInventory:
    profile_digests: dict[str, str]
    skill_digests: dict[str, str]
    profile_states: dict[str, AdmissionEvidenceState]
    skill_states: dict[str, AdmissionEvidenceState]
    blockers: tuple[str, ...]
    ready: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/eval-readiness-inventory/v1",
            "profile_digests": dict(sorted(self.profile_digests.items())),
            "skill_digests": dict(sorted(self.skill_digests.items())),
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


class EvalInventoryBuilder:
    def __init__(self, store: EvalEvidenceStore) -> None:
        self._store = store

    def build(
        self,
        *,
        profile_artifacts: Mapping[str, Path],
        skill_artifacts: Mapping[str, Path],
        scheduled_profile_ids: Iterable[str],
    ) -> EvalReadinessInventory:
        scheduled = frozenset(scheduled_profile_ids)
        profile_digests = {
            identity: digest_artifact(profile_artifacts[identity])
            for identity in sorted(profile_artifacts)
        }
        skill_digests = {
            identity: digest_artifact(skill_artifacts[identity])
            for identity in sorted(skill_artifacts)
        }
        profile_states = {
            identity: self._store.profile_admission_state(
                identity,
                digest,
                scheduled_duties=identity in scheduled,
            )
            for identity, digest in profile_digests.items()
        }
        skill_states = {
            identity: self._store.skill_admission_state(identity, digest)
            for identity, digest in skill_digests.items()
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
        return EvalReadinessInventory(
            profile_digests=profile_digests,
            skill_digests=skill_digests,
            profile_states=profile_states,
            skill_states=skill_states,
            blockers=blockers,
            ready=not blockers,
        )
