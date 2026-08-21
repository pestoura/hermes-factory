from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlanBuilder
from hermes_factory.governance.eval_inventory import (
    EvalInventoryBuilder,
    discover_skill_artifacts,
)
from hermes_factory.traceability.registry import SemanticRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_static_profile_batch_executes_51_checks_without_fabricating_behavioral_passes(
    tmp_path,
):
    from hermes_factory.governance.static_profile_evals import execute_static_profile_evals

    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    registry_document = yaml.safe_load((ROOT / "skills/registry.yaml").read_text())
    registry = registry_document["registry"]
    runtime_policies = yaml.safe_load(
        (ROOT / "agents/_shared/runtime-policies.yaml").read_text()
    )
    skill_artifacts = discover_skill_artifacts(ROOT / "skills", registry)

    profile_artifacts = {}
    agent_documents = {}
    for agent_id in catalog["active_candidates"]:
        agent_document = yaml.safe_load(
            (ROOT / "agents" / agent_id / "agent.yaml").read_text()
        )
        agent_documents[agent_id] = agent_document
        out = tmp_path / "profiles" / agent_id
        compile_profile_distribution(
            agent_document,
            (ROOT / "agents" / agent_id / "SOUL.md").read_text(),
            registry_document,
            out,
            cron_jobs=[],
            skill_artifacts=skill_artifacts,
            runtime_policies=runtime_policies,
        )
        profile_artifacts[agent_id] = out

    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    report = execute_static_profile_evals(
        store,
        profile_artifacts=profile_artifacts,
        agent_documents=agent_documents,
        skill_registry=registry_document,
        runtime_policies=runtime_policies,
        evidence_ref="ci:static-profile-eval-batch",
    )

    assert report.candidate_count == 17
    assert report.evidence_count == 51
    assert report.passed_count == 51
    assert report.failed_count == 0
    assert report.state == "PASS"

    inventory = EvalInventoryBuilder(store).build(
        profile_artifacts=profile_artifacts,
        skill_artifacts=skill_artifacts,
        scheduled_profile_ids=(),
    )
    execution_plan = EvalExecutionPlanBuilder(store).build(
        inventory,
        scheduled_profile_ids=(),
    )

    assert execution_plan.execution_state == "NOT_RUN"
    assert execution_plan.blockers == ()
    assert len(execution_plan.items) == 247
    assert sum(item.candidate_kind == "PROFILE" for item in execution_plan.items) == 102
    assert sum(item.candidate_kind == "SKILL" for item in execution_plan.items) == 145
