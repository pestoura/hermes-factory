from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState


def _item(
    kind: str,
    candidate_id: str,
    check: str,
    *,
    independent: bool = False,
) -> EvalWorkItem:
    return EvalWorkItem(
        candidate_kind=kind,
        candidate_id=candidate_id,
        candidate_digest=("p" if kind == "PROFILE" else "s") * 64,
        check=check,
        requires_independent_reviewer=independent,
    )


def test_automated_plan_selection_separates_independent_review() -> None:
    from hermes_factory.governance.behavioral_eval_execution import (
        select_automated_eval_plan,
    )

    profile = _item("PROFILE", "factory-software-engineer", "routing_correctness")
    skill = _item("SKILL", "factory-tdd-red", "skill_green")
    profile_review = _item(
        "PROFILE",
        "factory-software-engineer",
        "independent_review",
        independent=True,
    )
    skill_review = _item(
        "SKILL",
        "factory-tdd-red",
        "independent_review",
        independent=True,
    )
    source = EvalExecutionPlan(
        items=(profile, profile_review, skill, skill_review),
        blockers=(),
        execution_state="NOT_RUN",
        execute=False,
    )

    selection = select_automated_eval_plan(source)

    assert selection.automated_plan.items == (profile, skill)
    assert selection.automated_plan.blockers == ()
    assert selection.automated_plan.execution_state == "NOT_RUN"
    assert selection.automated_plan.execute is False
    assert selection.independent_review_items == (profile_review, skill_review)
    assert selection.source_item_count == 4
    assert selection.automated_item_count == 2
    assert selection.independent_review_count == 2


def test_automated_plan_selection_refuses_blocked_source_plan() -> None:
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        select_automated_eval_plan,
    )

    source = EvalExecutionPlan(
        items=(),
        blockers=("Skill factory-demo skill_green=FAIL",),
        execution_state="BLOCKED",
        execute=False,
    )

    try:
        select_automated_eval_plan(source)
    except BehavioralEvalExecutionError as error:
        assert "BLOCKED" in str(error)
    else:
        raise AssertionError("blocked source plan must fail closed")


def test_composite_runtime_routes_profile_and_skill_without_cross_calls() -> None:
    from hermes_factory.governance.behavioral_eval_execution import (
        CompositeBehavioralEvalRuntime,
    )

    profile_item = _item(
        "PROFILE", "factory-software-engineer", "routing_correctness"
    )
    skill_item = _item("SKILL", "factory-tdd-red", "skill_green")

    class ProfileRuntime:
        def __init__(self) -> None:
            self.items: list[EvalWorkItem] = []

        def evaluate(self, item: EvalWorkItem) -> ProfileEvalEvidence:
            self.items.append(item)
            return ProfileEvalEvidence(
                profile_id=item.candidate_id,
                profile_digest=item.candidate_digest,
                dimension=item.check,
                state=ProfileEvalState.PASS,
                evidence_ref="profile-runtime:evidence",
                evaluator="profile-runtime",
            )

    class SkillRuntime:
        def __init__(self) -> None:
            self.items: list[EvalWorkItem] = []

        def evaluate(self, item: EvalWorkItem) -> SkillEvalEvidence:
            self.items.append(item)
            return SkillEvalEvidence(
                skill_id=item.candidate_id,
                source_digest=item.candidate_digest,
                gate=item.check,
                state=SkillEvalState.PASS,
                evidence_ref="skill-runtime:evidence",
                evaluator="skill-runtime",
            )

    profiles = ProfileRuntime()
    skills = SkillRuntime()
    runtime = CompositeBehavioralEvalRuntime(
        profile_runtime=profiles,
        skill_runtime=skills,
    )

    assert isinstance(runtime.evaluate(profile_item), ProfileEvalEvidence)
    assert isinstance(runtime.evaluate(skill_item), SkillEvalEvidence)
    assert profiles.items == [profile_item]
    assert skills.items == [skill_item]


def test_composite_runtime_refuses_independent_review_before_delegation() -> None:
    from hermes_factory.governance.behavioral_eval_execution import (
        BehavioralEvalExecutionError,
        CompositeBehavioralEvalRuntime,
    )

    review = _item(
        "PROFILE",
        "factory-code-reviewer",
        "independent_review",
        independent=True,
    )

    class NeverRuntime:
        def __init__(self) -> None:
            self.called = False

        def evaluate(self, item: EvalWorkItem):
            self.called = True
            raise AssertionError(f"must not delegate independent review: {item}")

    profiles = NeverRuntime()
    skills = NeverRuntime()
    runtime = CompositeBehavioralEvalRuntime(
        profile_runtime=profiles,
        skill_runtime=skills,
    )

    try:
        runtime.evaluate(review)
    except BehavioralEvalExecutionError as error:
        assert "independent" in str(error).lower()
    else:
        raise AssertionError("independent review must not be automated")

    assert profiles.called is False
    assert skills.called is False
