from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from hermes_factory.agents.evals import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState


class BehavioralEvalExecutionError(ValueError):
    pass


EvalEvidence: TypeAlias = ProfileEvalEvidence | SkillEvalEvidence


class BehavioralEvalRuntime(Protocol):
    def evaluate(self, item: EvalWorkItem) -> EvalEvidence: ...


@dataclass(frozen=True)
class BehavioralEvalExecutionReport:
    attempted_count: int
    recorded_count: int
    passed_count: int
    failed_count: int
    state: str
    execute: bool


class BehavioralEvalExecutor:
    """Execute a prepared evaluation plan through an injected runtime boundary.

    The executor does not provide a Hermes implementation. It validates that
    runtime evidence is bound to the exact work item before persisting it in the
    canonical immutable evidence store.
    """

    def __init__(self, store: EvalEvidenceStore, runtime: BehavioralEvalRuntime) -> None:
        self._store = store
        self._runtime = runtime

    @staticmethod
    def _validate_profile(
        item: EvalWorkItem,
        evidence: ProfileEvalEvidence,
    ) -> None:
        if evidence.profile_id != item.candidate_id:
            raise BehavioralEvalExecutionError("Profile evidence candidate does not match work item")
        if evidence.profile_digest != item.candidate_digest:
            raise BehavioralEvalExecutionError("Profile evidence digest does not match work item")
        if evidence.dimension != item.check:
            raise BehavioralEvalExecutionError("Profile evidence check does not match work item")
        if evidence.state is ProfileEvalState.NOT_RUN:
            raise BehavioralEvalExecutionError("executed Profile evidence cannot be NOT_RUN")

    @staticmethod
    def _validate_skill(item: EvalWorkItem, evidence: SkillEvalEvidence) -> None:
        if evidence.skill_id != item.candidate_id:
            raise BehavioralEvalExecutionError("Skill evidence candidate does not match work item")
        if evidence.source_digest != item.candidate_digest:
            raise BehavioralEvalExecutionError("Skill evidence digest does not match work item")
        if evidence.gate != item.check:
            raise BehavioralEvalExecutionError("Skill evidence check does not match work item")
        if evidence.state is SkillEvalState.NOT_RUN:
            raise BehavioralEvalExecutionError("executed Skill evidence cannot be NOT_RUN")

    def execute(self, plan: EvalExecutionPlan) -> BehavioralEvalExecutionReport:
        if plan.blockers or plan.execution_state == "BLOCKED":
            raise BehavioralEvalExecutionError("evaluation plan is BLOCKED")
        if plan.execution_state not in {"NOT_RUN", "PASS"}:
            raise BehavioralEvalExecutionError(
                f"unsupported evaluation execution state: {plan.execution_state}"
            )

        attempted_count = 0
        recorded_count = 0
        passed_count = 0
        failed_count = 0

        for item in plan.items:
            if item.candidate_kind not in {"PROFILE", "SKILL"}:
                raise BehavioralEvalExecutionError(
                    f"unknown evaluation candidate kind: {item.candidate_kind}"
                )

            attempted_count += 1
            evidence = self._runtime.evaluate(item)

            if item.candidate_kind == "PROFILE":
                if not isinstance(evidence, ProfileEvalEvidence):
                    raise BehavioralEvalExecutionError(
                        "runtime returned non-Profile evidence for Profile work item"
                    )
                self._validate_profile(item, evidence)
                self._store.record_profile(evidence)
                if evidence.state is ProfileEvalState.PASS:
                    passed_count += 1
                else:
                    failed_count += 1
            else:
                if not isinstance(evidence, SkillEvalEvidence):
                    raise BehavioralEvalExecutionError(
                        "runtime returned non-Skill evidence for Skill work item"
                    )
                self._validate_skill(item, evidence)
                self._store.record_skill(evidence)
                if evidence.state is SkillEvalState.PASS:
                    passed_count += 1
                else:
                    failed_count += 1

            recorded_count += 1

        return BehavioralEvalExecutionReport(
            attempted_count=attempted_count,
            recorded_count=recorded_count,
            passed_count=passed_count,
            failed_count=failed_count,
            state="FAIL" if failed_count else "PASS",
            execute=True,
        )
