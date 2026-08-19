from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from hermes_factory.agents.evals import ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_inventory import EvalReadinessInventory
from hermes_factory.skills.evals import SkillEvalState


class EvalExecutionPlanError(ValueError):
    pass


@dataclass(frozen=True)
class EvalWorkItem:
    candidate_kind: str
    candidate_id: str
    candidate_digest: str
    check: str
    requires_independent_reviewer: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "candidate_kind": self.candidate_kind,
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "check": self.check,
            "requires_independent_reviewer": self.requires_independent_reviewer,
        }


@dataclass(frozen=True)
class EvalExecutionPlan:
    items: tuple[EvalWorkItem, ...]
    blockers: tuple[str, ...]
    execution_state: str
    execute: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/eval-execution-plan/v1",
            "items": [item.to_manifest() for item in self.items],
            "blockers": list(self.blockers),
            "execution_state": self.execution_state,
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


class EvalExecutionPlanBuilder:
    def __init__(self, store: EvalEvidenceStore) -> None:
        self._store = store

    def build(
        self,
        inventory: EvalReadinessInventory,
        *,
        scheduled_profile_ids: Iterable[str],
    ) -> EvalExecutionPlan:
        scheduled = frozenset(scheduled_profile_ids)
        unknown_scheduled = sorted(scheduled - set(inventory.profile_digests))
        if unknown_scheduled:
            raise EvalExecutionPlanError(
                f"scheduled Profile(s) absent from eval inventory: {unknown_scheduled}"
            )

        items: list[EvalWorkItem] = []
        blockers: list[str] = []

        for profile_id, profile_digest in sorted(inventory.profile_digests.items()):
            record = self._store.profile_record(
                profile_id,
                profile_digest,
                scheduled_duties=profile_id in scheduled,
            )
            for dimension, state in sorted(record.required_states.items()):
                if state is ProfileEvalState.FAIL:
                    blockers.append(f"Profile {profile_id} {dimension}=FAIL")
                elif state is ProfileEvalState.NOT_RUN:
                    items.append(
                        EvalWorkItem(
                            candidate_kind="PROFILE",
                            candidate_id=profile_id,
                            candidate_digest=profile_digest,
                            check=dimension,
                            requires_independent_reviewer=dimension == "independent_review",
                        )
                    )

        for skill_id, source_digest in sorted(inventory.skill_digests.items()):
            states = self._store.skill_gate_states(skill_id, source_digest)
            for gate, state in sorted(states.items()):
                if state is SkillEvalState.FAIL:
                    blockers.append(f"Skill {skill_id} {gate}=FAIL")
                elif state is SkillEvalState.NOT_RUN:
                    items.append(
                        EvalWorkItem(
                            candidate_kind="SKILL",
                            candidate_id=skill_id,
                            candidate_digest=source_digest,
                            check=gate,
                            requires_independent_reviewer=gate == "independent_review",
                        )
                    )

        ordered_items = tuple(
            sorted(
                items,
                key=lambda item: (
                    item.candidate_kind,
                    item.candidate_id,
                    item.check,
                ),
            )
        )
        ordered_blockers = tuple(sorted(blockers))
        if ordered_blockers:
            execution_state = "BLOCKED"
        elif ordered_items:
            execution_state = "NOT_RUN"
        else:
            execution_state = "PASS"

        return EvalExecutionPlan(
            items=ordered_items,
            blockers=ordered_blockers,
            execution_state=execution_state,
            execute=False,
        )
