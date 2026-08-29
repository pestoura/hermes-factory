from hermes_factory.agents.evals import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_inventory import EvalInventoryBuilder
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.traceability.registry import SemanticRegistry


def _plan_contract():
    try:
        from hermes_factory.governance.eval_execution import EvalExecutionPlanBuilder
    except ModuleNotFoundError as exc:
        raise AssertionError("digest-bound eval execution plan is not implemented") from exc
    return EvalExecutionPlanBuilder


def _inventory(tmp_path, store):
    profile = tmp_path / "profile"
    skill = tmp_path / "SKILL.md"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n")
    skill.write_text("# Skill\n")
    return EvalInventoryBuilder(store).build(
        profile_artifacts={"factory-orchestrator": profile},
        skill_artifacts={"factory-reading-project-truth": skill},
        scheduled_profile_ids=(),
    )


def test_eval_execution_plan_lists_every_not_run_dimension_and_gate(tmp_path) -> None:
    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = _inventory(tmp_path, store)

    plan = _plan_contract()(store).build(
        inventory,
        scheduled_profile_ids=(),
    )

    profile_items = [item for item in plan.items if item.candidate_kind == "PROFILE"]
    skill_items = [item for item in plan.items if item.candidate_kind == "SKILL"]
    assert len(profile_items) == 10
    assert len(skill_items) == 5
    assert {item.candidate_digest for item in profile_items} == {
        inventory.profile_digests["factory-orchestrator"]
    }
    assert {item.candidate_digest for item in skill_items} == {
        inventory.skill_digests["factory-reading-project-truth"]
    }
    assert plan.execute is False
    assert plan.execution_state == "NOT_RUN"
    assert len(plan.digest) == 64


def test_eval_execution_plan_omits_already_passed_checks(tmp_path) -> None:
    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = _inventory(tmp_path, store)
    profile_digest = inventory.profile_digests["factory-orchestrator"]
    skill_digest = inventory.skill_digests["factory-reading-project-truth"]

    store.record_profile(
        ProfileEvalEvidence(
            profile_id="factory-orchestrator",
            profile_digest=profile_digest,
            dimension="tool_policy_projection",
            state=ProfileEvalState.PASS,
            evidence_ref="ci://profile/tool-policy/1",
            evaluator="factory-evidence-auditor",
        )
    )
    store.record_skill(
        SkillEvalEvidence(
            skill_id="factory-reading-project-truth",
            source_digest=skill_digest,
            gate="baseline_red",
            state=SkillEvalState.PASS,
            evidence_ref="ci://skill/baseline-red/1",
            evaluator="factory-integration-tester",
        )
    )

    plan = _plan_contract()(store).build(
        inventory,
        scheduled_profile_ids=(),
    )

    checks = {(item.candidate_kind, item.check) for item in plan.items}
    assert ("PROFILE", "tool_policy_projection") not in checks
    assert ("SKILL", "baseline_red") not in checks
    assert len(plan.items) == 13


def test_eval_execution_plan_is_deterministic(tmp_path) -> None:
    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = _inventory(tmp_path, store)
    builder = _plan_contract()(store)

    first = builder.build(inventory, scheduled_profile_ids=())
    second = builder.build(inventory, scheduled_profile_ids=())

    assert first.to_manifest() == second.to_manifest()
    assert first.digest == second.digest
