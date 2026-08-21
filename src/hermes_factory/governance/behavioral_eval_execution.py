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
class AutomatedEvalPlanSelection:
    automated_plan: EvalExecutionPlan
    independent_review_items: tuple[EvalWorkItem, ...]
    source_item_count: int

    @property
    def automated_item_count(self) -> int:
        return len(self.automated_plan.items)

    @property
    def independent_review_count(self) -> int:
        return len(self.independent_review_items)


@dataclass(frozen=True)
class BehavioralEvalExecutionReport:
    attempted_count: int
    recorded_count: int
    passed_count: int
    failed_count: int
    state: str
    execute: bool


class CompositeBehavioralEvalRuntime:
    """Route automatable Profile and Skill work to their dedicated runtimes.

    Independent review is a human assurance boundary and is rejected before
    either delegate is called. The executor still validates exact candidate
    identity and evidence type after each delegated evaluation.
    """

    def __init__(
        self,
        *,
        profile_runtime: BehavioralEvalRuntime,
        skill_runtime: BehavioralEvalRuntime,
    ) -> None:
        self._profile_runtime = profile_runtime
        self._skill_runtime = skill_runtime

    def evaluate(self, item: EvalWorkItem) -> EvalEvidence:
        if item.requires_independent_reviewer or item.check == "independent_review":
            raise BehavioralEvalExecutionError(
                "independent review cannot be delegated to automated evaluation runtime"
            )
        if item.candidate_kind == "PROFILE":
            return self._profile_runtime.evaluate(item)
        if item.candidate_kind == "SKILL":
            return self._skill_runtime.evaluate(item)
        raise BehavioralEvalExecutionError(
            f"unknown evaluation candidate kind: {item.candidate_kind}"
        )


def select_automated_eval_plan(plan: EvalExecutionPlan) -> AutomatedEvalPlanSelection:
    """Partition one canonical plan into automatable work and human review.

    The source plan remains authoritative. This function creates a bounded
    executable projection containing only non-independent work while returning
    the human-review items separately. A blocked or internally inconsistent
    source plan fails closed.
    """

    if plan.blockers or plan.execution_state == "BLOCKED":
        raise BehavioralEvalExecutionError("evaluation plan is BLOCKED")
    if plan.execution_state not in {"NOT_RUN", "PASS"}:
        raise BehavioralEvalExecutionError(
            f"unsupported evaluation execution state: {plan.execution_state}"
        )
    if plan.execution_state == "PASS" and plan.items:
        raise BehavioralEvalExecutionError(
            "evaluation plan is PASS but still contains pending work items"
        )

    automated: list[EvalWorkItem] = []
    independent: list[EvalWorkItem] = []
    for item in plan.items:
        check_is_independent = item.check == "independent_review"
        if item.requires_independent_reviewer != check_is_independent:
            raise BehavioralEvalExecutionError(
                "independent review marker does not match evaluation check"
            )
        if check_is_independent:
            independent.append(item)
        else:
            automated.append(item)

    automated_items = tuple(automated)
    automated_plan = EvalExecutionPlan(
        items=automated_items,
        blockers=(),
        execution_state="NOT_RUN" if automated_items else "PASS",
        execute=False,
    )
    return AutomatedEvalPlanSelection(
        automated_plan=automated_plan,
        independent_review_items=tuple(independent),
        source_item_count=len(plan.items),
    )


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
        if plan.execution_state == "PASS" and plan.items:
            raise BehavioralEvalExecutionError(
                "evaluation plan is PASS but still contains pending work items"
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
