from pathlib import Path

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.traceability.registry import SemanticRegistry


class FakeEvalRuntime:
    def __init__(self) -> None:
        self.items: list[EvalWorkItem] = []

    def evaluate(self, item: EvalWorkItem):
        self.items.append(item)
        if item.candidate_kind == "PROFILE":
            return ProfileEvalEvidence(
                profile_id=item.candidate_id,
                profile_digest=item.candidate_digest,
                dimension=item.check,
                state=ProfileEvalState.PASS,
                evidence_ref=f"runtime:{item.candidate_id}:{item.check}",
                evaluator="factory-evidence-auditor",
            )
        return SkillEvalEvidence(
            skill_id=item.candidate_id,
            source_digest=item.candidate_digest,
            gate=item.check,
            state=SkillEvalState.PASS,
            evidence_ref=f"runtime:{item.candidate_id}:{item.check}",
            evaluator="factory-fail-closed-inspector",
        )


def _store(path: Path) -> EvalEvidenceStore:
    return EvalEvidenceStore(SemanticRegistry(path))


def test_behavioral_executor_records_exact_candidate_runtime_evidence(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import BehavioralEvalExecutor

    profile = EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        candidate_digest="p" * 64,
        check="routing_correctness",
        requires_independent_reviewer=False,
    )
    skill = EvalWorkItem(
        candidate_kind="SKILL",
        candidate_id="factory-tdd-red",
        candidate_digest="s" * 64,
        check="pressure_eval",
        requires_independent_reviewer=False,
    )
    plan = EvalExecutionPlan(
        items=(profile, skill), blockers=(), execution_state="NOT_RUN", execute=False
    )
    runtime = FakeEvalRuntime()
    store = _store(tmp_path / "factory.db")

    report = BehavioralEvalExecutor(store, runtime).execute(plan)

    assert runtime.items == [profile, skill]
    assert report.attempted_count == 2
    assert report.recorded_count == 2
    assert report.passed_count == 2
    assert report.failed_count == 0
    assert report.state == "PASS"
    assert report.execute is True
    assert store.profile_record(
        profile.candidate_id, profile.candidate_digest, scheduled_duties=False
    ).required_states[profile.check] is ProfileEvalState.PASS
    assert store.skill_gate_states(skill.candidate_id, skill.candidate_digest)[
        skill.check
    ] is SkillEvalState.PASS


def test_behavioral_executor_refuses_blocked_plan_without_runtime_calls(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        BehavioralEvalExecutor,
    )

    plan = EvalExecutionPlan(
        items=(),
        blockers=("Profile factory-demo routing_correctness=FAIL",),
        execution_state="BLOCKED",
        execute=False,
    )
    runtime = FakeEvalRuntime()

    try:
        BehavioralEvalExecutor(_store(tmp_path / "factory.db"), runtime).execute(plan)
    except BehavioralEvalExecutionError as error:
        assert "BLOCKED" in str(error)
    else:
        raise AssertionError("expected blocked eval execution to fail closed")

    assert runtime.items == []


def test_behavioral_executor_rejects_evidence_for_another_candidate(tmp_path):
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        BehavioralEvalExecutor,
    )

    item = EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-code-reviewer",
        candidate_digest="d" * 64,
        check="routing_correctness",
        requires_independent_reviewer=False,
    )
    plan = EvalExecutionPlan(
        items=(item,), blockers=(), execution_state="NOT_RUN", execute=False
    )

    class WrongRuntime:
        def evaluate(self, work_item: EvalWorkItem):
            return ProfileEvalEvidence(
                profile_id="factory-software-engineer",
                profile_digest=work_item.candidate_digest,
                dimension=work_item.check,
                state=ProfileEvalState.PASS,
                evidence_ref="runtime:wrong-candidate",
                evaluator="factory-evidence-auditor",
            )

    try:
        BehavioralEvalExecutor(_store(tmp_path / "factory.db"), WrongRuntime()).execute(
            plan
        )
    except BehavioralEvalExecutionError as error:
        assert "candidate" in str(error)
    else:
        raise AssertionError("expected mismatched evidence to fail closed")
