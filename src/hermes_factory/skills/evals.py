from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hermes_factory.skills.system import SkillAdmissionError, SkillEvalRecord


class SkillEvalState(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class SkillEvalEvidence:
    skill_id: str
    source_digest: str
    gate: str
    state: SkillEvalState
    evidence_ref: str
    evaluator: str


_GATES = (
    "baseline_red",
    "skill_green",
    "variation_eval",
    "pressure_eval",
    "independent_review",
)


class SkillEvalHarness:
    def evaluate(
        self,
        skill_id: str,
        source_digest: str,
        evidence: tuple[SkillEvalEvidence, ...],
    ) -> SkillEvalRecord:
        if not skill_id.strip() or not source_digest.strip():
            raise SkillAdmissionError("skill_id and source digest are required")
        states: dict[str, SkillEvalState] = {}
        for record in evidence:
            if record.skill_id != skill_id:
                raise SkillAdmissionError(
                    "evaluation evidence belongs to another Skill"
                )
            if record.source_digest != source_digest:
                raise SkillAdmissionError(
                    "evaluation evidence source digest does not match current Skill"
                )
            if record.gate not in _GATES:
                raise SkillAdmissionError(
                    f"unknown Skill evaluation gate {record.gate}"
                )
            if record.gate in states:
                raise SkillAdmissionError(
                    f"duplicate evidence for Skill evaluation gate {record.gate}"
                )
            if not record.evidence_ref.strip() or not record.evaluator.strip():
                raise SkillAdmissionError("evaluation evidence requires provenance")
            states[record.gate] = record.state
        passed = {
            gate: states.get(gate) is SkillEvalState.PASS
            for gate in _GATES
        }
        return SkillEvalRecord(
            baseline_red=passed["baseline_red"],
            skill_green=passed["skill_green"],
            variation_eval=passed["variation_eval"],
            pressure_eval=passed["pressure_eval"],
            independent_review=passed["independent_review"],
        )
