from pathlib import Path

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.traceability.registry import SemanticRegistry


def _store(path: Path) -> EvalEvidenceStore:
    return EvalEvidenceStore(SemanticRegistry(path))


def _profile_item(check: str = "routing_correctness") -> EvalWorkItem:
    return EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        candidate_digest="a" * 64,
        check=check,
        requires_independent_reviewer=check == "independent_review",
    )


def test_behavioral_executor_rejects_not_run_as_runtime_result(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        BehavioralEvalExecutor,
    )

    item = _profile_item()

    class NotRunRuntime:
        def evaluate(self, work_item: EvalWorkItem):
            return ProfileEvalEvidence(
                profile_id=work_item.candidate_id,
                profile_digest=work_item.candidate_digest,
                dimension=work_item.check,
                state=ProfileEvalState.NOT_RUN,
                evidence_ref="runtime:not-run",
                evaluator="factory-evidence-auditor",
            )

    plan = EvalExecutionPlan(
        items=(item,), blockers=(), execution_state="NOT_RUN", execute=False
    )
    store = _store(tmp_path / "factory.db")

    try:
        BehavioralEvalExecutor(store, NotRunRuntime()).execute(plan)
    except BehavioralEvalExecutionError as error:
        assert "NOT_RUN" in str(error)
    else:
        raise AssertionError("executed evidence must not remain NOT_RUN")

    assert store.profile_record(
        item.candidate_id, item.candidate_digest, scheduled_duties=False
    ).required_states[item.check] is ProfileEvalState.NOT_RUN


def test_behavioral_executor_rejects_inconsistent_pass_plan_before_runtime(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        BehavioralEvalExecutor,
    )

    item = _profile_item()

    class CountingRuntime:
        def __init__(self) -> None:
            self.calls = 0

        def evaluate(self, work_item: EvalWorkItem):
            self.calls += 1
            return ProfileEvalEvidence(
                profile_id=work_item.candidate_id,
                profile_digest=work_item.candidate_digest,
                dimension=work_item.check,
                state=ProfileEvalState.PASS,
                evidence_ref="runtime:unexpected",
                evaluator="factory-evidence-auditor",
            )

    runtime = CountingRuntime()
    plan = EvalExecutionPlan(
        items=(item,), blockers=(), execution_state="PASS", execute=False
    )

    try:
        BehavioralEvalExecutor(_store(tmp_path / "factory.db"), runtime).execute(plan)
    except BehavioralEvalExecutionError as error:
        assert "PASS" in str(error)
    else:
        raise AssertionError("PASS plan with pending items must fail closed")

    assert runtime.calls == 0


def test_behavioral_executor_cannot_bypass_independent_review_separation(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import BehavioralEvalExecutor

    item = _profile_item("independent_review")

    class SelfReviewRuntime:
        def evaluate(self, work_item: EvalWorkItem):
            return ProfileEvalEvidence(
                profile_id=work_item.candidate_id,
                profile_digest=work_item.candidate_digest,
                dimension=work_item.check,
                state=ProfileEvalState.PASS,
                evidence_ref="runtime:self-review",
                evaluator=work_item.candidate_id,
            )

    plan = EvalExecutionPlan(
        items=(item,), blockers=(), execution_state="NOT_RUN", execute=False
    )
    store = _store(tmp_path / "factory.db")

    try:
        BehavioralEvalExecutor(store, SelfReviewRuntime()).execute(plan)
    except ValueError as error:
        assert "independent review" in str(error)
    else:
        raise AssertionError("self-review must fail closed")

    assert store.profile_record(
        item.candidate_id, item.candidate_digest, scheduled_duties=False
    ).required_states[item.check] is ProfileEvalState.NOT_RUN
