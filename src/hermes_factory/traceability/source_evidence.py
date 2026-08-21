from __future__ import annotations

import hashlib
import json
from typing import Any

from hermes_factory.adapters.jds import JDSEffectiveGatePlan
from hermes_factory.agents.evals import ProfileEvalEvidence, ProfileEvalRecord
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.skills.system import SkillEvalRecord
from hermes_factory.traceability.registry import SemanticRegistry

_SKILL_GATES = (
    "baseline_red",
    "skill_green",
    "variation_eval",
    "pressure_eval",
    "independent_review",
)


def _evidence_id(kind: str, *parts: str) -> str:
    encoded = json.dumps(
        (kind, *parts),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"factory-source:{kind.lower()}:{hashlib.sha256(encoded).hexdigest()}"


def _overall_state(states: tuple[str, ...]) -> str:
    if "FAIL" in states:
        return "FAIL"
    if states and all(state == "PASS" for state in states):
        return "PASS"
    return "NOT_RUN"


class FactorySourceEvidenceRecorder:
    """Persist canonical source evidence consumed by the Factory Dashboard."""

    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def record_jds_gate_plan(
        self,
        *,
        candidate: str,
        plan: JDSEffectiveGatePlan,
    ) -> str:
        evidence_id = _evidence_id("JDS_GATE_PLAN", candidate, plan.plan_digest)
        payload: dict[str, Any] = {
            "source": plan.source,
            "schema": plan.schema,
            "standard": plan.standard,
            "platform_ref": plan.platform_ref,
            "criticality": plan.criticality,
            "change_source": plan.change_source,
            "ambiguous_impact": plan.ambiguous_impact,
            "effective_capabilities": list(plan.effective_capabilities),
            "selected_capabilities": list(plan.selected_capabilities),
            "selected_gates": list(plan.selected_gates),
            "skipped_capabilities": dict(plan.skipped_capabilities),
            "plan_digest": plan.plan_digest,
        }
        self._registry.record_evidence(
            evidence_id,
            kind="JDS_GATE_PLAN",
            state="OBSERVED",
            candidate=candidate,
            payload=payload,
        )
        return evidence_id

    def record_profile_evaluation(
        self,
        *,
        candidate: str,
        evaluation: ProfileEvalRecord,
        evidence: tuple[ProfileEvalEvidence, ...],
    ) -> str:
        required_states = {
            dimension: state.value
            for dimension, state in evaluation.required_states.items()
        }
        provenance = {
            item.dimension: {
                "evidence_ref": item.evidence_ref,
                "evaluator": item.evaluator,
            }
            for item in evidence
        }
        state = _overall_state(tuple(required_states.values()))
        evidence_id = _evidence_id(
            "PROFILE_EVAL",
            candidate,
            evaluation.profile_id,
            evaluation.profile_digest,
        )
        self._registry.record_evidence(
            evidence_id,
            kind="PROFILE_EVAL",
            state=state,
            candidate=candidate,
            payload={
                "profile_id": evaluation.profile_id,
                "profile_digest": evaluation.profile_digest,
                "required_states": required_states,
                "provenance": provenance,
                "eligible_for_activation": evaluation.eligible_for_activation,
            },
        )
        return evidence_id

    def record_skill_evaluation(
        self,
        *,
        candidate: str,
        skill_id: str,
        source_digest: str,
        evaluation: SkillEvalRecord,
        evidence: tuple[SkillEvalEvidence, ...],
    ) -> str:
        gate_states = {gate: SkillEvalState.NOT_RUN.value for gate in _SKILL_GATES}
        provenance: dict[str, dict[str, str]] = {}
        for item in evidence:
            gate_states[item.gate] = item.state.value
            provenance[item.gate] = {
                "evidence_ref": item.evidence_ref,
                "evaluator": item.evaluator,
            }

        state = _overall_state(tuple(gate_states.values()))
        evidence_id = _evidence_id(
            "SKILL_EVAL",
            candidate,
            skill_id,
            source_digest,
        )
        self._registry.record_evidence(
            evidence_id,
            kind="SKILL_EVAL",
            state=state,
            candidate=candidate,
            payload={
                "skill_id": skill_id,
                "source_digest": source_digest,
                "gate_states": gate_states,
                "provenance": provenance,
                "promotable": evaluation.promotable,
            },
        )
        return evidence_id
