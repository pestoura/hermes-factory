from __future__ import annotations

from hermes_factory.agents.evals import (
    ProfileEvalEvidence,
    ProfileEvalHarness,
    ProfileEvalRecord,
    ProfileEvalState,
)
from hermes_factory.runtime.admission import AdmissionEvidenceState
from hermes_factory.skills.evals import (
    SKILL_EVAL_GATES,
    SkillEvalEvidence,
    SkillEvalHarness,
    SkillEvalState,
)
from hermes_factory.skills.system import SkillEvalRecord
from hermes_factory.traceability.registry import SemanticRegistry

_PROFILE_KIND = "PROFILE_EVAL"
_SKILL_KIND = "SKILL_EVAL"


def _profile_candidate(profile_id: str, profile_digest: str) -> str:
    return f"profile:{profile_id}:{profile_digest}"


def _skill_candidate(skill_id: str, source_digest: str) -> str:
    return f"skill:{skill_id}:{source_digest}"


class EvalEvidenceStore:
    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry
        self._profile_harness = ProfileEvalHarness()
        self._skill_harness = SkillEvalHarness()

    def record_profile(self, evidence: ProfileEvalEvidence) -> None:
        # Reuse the canonical harness for identity, digest, dimension and
        # provenance validation before making evidence immutable.
        self._profile_harness.evaluate(
            evidence.profile_id,
            evidence.profile_digest,
            (evidence,),
            scheduled_duties=evidence.dimension == "native_cron_projection",
        )
        self._registry.record_evidence(
            f"profile-eval:{evidence.profile_id}:{evidence.profile_digest}:{evidence.dimension}",
            kind=_PROFILE_KIND,
            state=evidence.state.value,
            candidate=_profile_candidate(evidence.profile_id, evidence.profile_digest),
            payload={
                "profile_id": evidence.profile_id,
                "profile_digest": evidence.profile_digest,
                "dimension": evidence.dimension,
                "evidence_ref": evidence.evidence_ref,
                "evaluator": evidence.evaluator,
            },
        )

    def _profile_evidence(
        self,
        profile_id: str,
        profile_digest: str,
    ) -> tuple[ProfileEvalEvidence, ...]:
        rows = self._registry.list_evidence(
            candidate=_profile_candidate(profile_id, profile_digest)
        )
        return tuple(
            ProfileEvalEvidence(
                profile_id=str(row["payload"]["profile_id"]),
                profile_digest=str(row["payload"]["profile_digest"]),
                dimension=str(row["payload"]["dimension"]),
                state=ProfileEvalState(str(row["state"])),
                evidence_ref=str(row["payload"]["evidence_ref"]),
                evaluator=str(row["payload"]["evaluator"]),
            )
            for row in rows
            if row["kind"] == _PROFILE_KIND
        )

    def profile_record(
        self,
        profile_id: str,
        profile_digest: str,
        *,
        scheduled_duties: bool,
    ) -> ProfileEvalRecord:
        return self._profile_harness.evaluate(
            profile_id,
            profile_digest,
            self._profile_evidence(profile_id, profile_digest),
            scheduled_duties=scheduled_duties,
        )

    def profile_admission_state(
        self,
        profile_id: str,
        profile_digest: str,
        *,
        scheduled_duties: bool,
    ) -> AdmissionEvidenceState:
        record = self.profile_record(
            profile_id,
            profile_digest,
            scheduled_duties=scheduled_duties,
        )
        if any(state is ProfileEvalState.FAIL for state in record.required_states.values()):
            return AdmissionEvidenceState.FAIL
        if record.eligible_for_activation:
            return AdmissionEvidenceState.PASS
        return AdmissionEvidenceState.NOT_RUN

    def record_skill(self, evidence: SkillEvalEvidence) -> None:
        self._skill_harness.evaluate(
            evidence.skill_id,
            evidence.source_digest,
            (evidence,),
        )
        self._registry.record_evidence(
            f"skill-eval:{evidence.skill_id}:{evidence.source_digest}:{evidence.gate}",
            kind=_SKILL_KIND,
            state=evidence.state.value,
            candidate=_skill_candidate(evidence.skill_id, evidence.source_digest),
            payload={
                "skill_id": evidence.skill_id,
                "source_digest": evidence.source_digest,
                "gate": evidence.gate,
                "evidence_ref": evidence.evidence_ref,
                "evaluator": evidence.evaluator,
            },
        )

    def _skill_evidence(
        self,
        skill_id: str,
        source_digest: str,
    ) -> tuple[SkillEvalEvidence, ...]:
        rows = self._registry.list_evidence(
            candidate=_skill_candidate(skill_id, source_digest)
        )
        return tuple(
            SkillEvalEvidence(
                skill_id=str(row["payload"]["skill_id"]),
                source_digest=str(row["payload"]["source_digest"]),
                gate=str(row["payload"]["gate"]),
                state=SkillEvalState(str(row["state"])),
                evidence_ref=str(row["payload"]["evidence_ref"]),
                evaluator=str(row["payload"]["evaluator"]),
            )
            for row in rows
            if row["kind"] == _SKILL_KIND
        )

    def skill_gate_states(
        self,
        skill_id: str,
        source_digest: str,
    ) -> dict[str, SkillEvalState]:
        evidence = self._skill_evidence(skill_id, source_digest)
        by_gate = {record.gate: record.state for record in evidence}
        return {
            gate: by_gate.get(gate, SkillEvalState.NOT_RUN)
            for gate in SKILL_EVAL_GATES
        }

    def skill_record(self, skill_id: str, source_digest: str) -> SkillEvalRecord:
        return self._skill_harness.evaluate(
            skill_id,
            source_digest,
            self._skill_evidence(skill_id, source_digest),
        )

    def skill_admission_state(
        self,
        skill_id: str,
        source_digest: str,
    ) -> AdmissionEvidenceState:
        evidence = self._skill_evidence(skill_id, source_digest)
        if any(record.state is SkillEvalState.FAIL for record in evidence):
            return AdmissionEvidenceState.FAIL
        if self._skill_harness.evaluate(skill_id, source_digest, evidence).promotable:
            return AdmissionEvidenceState.PASS
        return AdmissionEvidenceState.NOT_RUN
