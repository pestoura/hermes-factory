from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.runtime.admission import AdmissionEvidenceState

_SKILL_GROUPS = (
    "core",
    "control_workforce",
    "product_architecture",
    "documentation",
    "engineering_quality",
    "security_assurance",
    "governance_operations",
)


class EvalInventoryError(ValueError):
    pass


def discover_skill_artifacts(
    skills_root: Path,
    registry: Mapping[str, Any],
) -> dict[str, Path]:
    aliases = registry.get("legacy_source_aliases", {})
    if not isinstance(aliases, dict):
        raise EvalInventoryError("legacy_source_aliases must be a mapping")

    superseded = registry.get("superseded_skill_concepts", {})
    if not isinstance(superseded, dict):
        raise EvalInventoryError("superseded_skill_concepts must be a mapping")

    expected: set[str] = set()
    for group in _SKILL_GROUPS:
        values = registry.get(group)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise EvalInventoryError(f"Skill registry group {group} must be a list of IDs")
        expected.update(values)

    discovered: dict[str, Path] = {}
    for skill_file in sorted(skills_root.glob("*/*/SKILL.md")):
        source_name = skill_file.parent.name
        if source_name in superseded:
            replacement = superseded[source_name]
            if not isinstance(replacement, dict) or not str(replacement.get("replaced_by", "")).startswith("gate:"):
                raise EvalInventoryError(
                    f"superseded Skill source {source_name} lacks deterministic gate replacement"
                )
            continue

        if source_name.startswith("factory-"):
            canonical_id = source_name
        else:
            alias = aliases.get(source_name)
            canonical_id = str(alias) if alias is not None else f"factory-{source_name}"

        if canonical_id not in expected:
            raise EvalInventoryError(
                f"Skill source {source_name} resolves to unregistered ID {canonical_id}"
            )
        if canonical_id in discovered:
            raise EvalInventoryError(f"duplicate Skill artifact for {canonical_id}")
        discovered[canonical_id] = skill_file.parent

    missing = sorted(expected - set(discovered))
    if missing:
        raise EvalInventoryError(f"missing canonical Skill artifact(s): {missing}")

    return dict(sorted(discovered.items()))


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
        unknown_scheduled = sorted(scheduled - set(profile_artifacts))
        if unknown_scheduled:
            raise EvalInventoryError(
                f"scheduled Profile(s) missing candidate artifact: {unknown_scheduled}"
            )

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
