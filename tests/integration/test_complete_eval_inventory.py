from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlanBuilder
from hermes_factory.governance.eval_inventory import (
    EvalInventoryBuilder,
    discover_skill_artifacts,
)
from hermes_factory.runtime.admission import AdmissionEvidenceState
from hermes_factory.traceability.registry import SemanticRegistry

ROOT = Path(__file__).resolve().parents[2]
_SKILL_GROUPS = (
    "core",
    "control_workforce",
    "product_architecture",
    "documentation",
    "engineering_quality",
    "security_assurance",
    "governance_operations",
)


def test_complete_profile_and_skill_catalogue_is_visible_to_eval_readiness(tmp_path):
    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    registry_document = yaml.safe_load((ROOT / "skills/registry.yaml").read_text())
    registry = registry_document["registry"]
    skill_artifacts = discover_skill_artifacts(ROOT / "skills", registry)

    profile_artifacts = {}
    for agent_id in catalog["active_candidates"]:
        out = tmp_path / "profiles" / agent_id
        compile_profile_distribution(
            yaml.safe_load((ROOT / "agents" / agent_id / "agent.yaml").read_text()),
            (ROOT / "agents" / agent_id / "SOUL.md").read_text(),
            registry_document,
            out,
            cron_jobs=[],
            skill_artifacts=skill_artifacts,
        )
        profile_artifacts[agent_id] = out

    expected_skill_ids = {
        skill_id
        for group in _SKILL_GROUPS
        for skill_id in registry[group]
    }

    assert len(profile_artifacts) == 17
    assert len(expected_skill_ids) == 29
    assert set(skill_artifacts) == expected_skill_ids
    assert set(registry["proposed_v1_2_skills"]) <= expected_skill_ids
    assert "factory-verifying-exact-sha" not in skill_artifacts

    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = EvalInventoryBuilder(store).build(
        profile_artifacts=profile_artifacts,
        skill_artifacts=skill_artifacts,
        scheduled_profile_ids=(),
    )

    assert set(inventory.profile_states) == set(catalog["active_candidates"])
    assert set(inventory.skill_states) == expected_skill_ids
    assert set(inventory.profile_states.values()) == {AdmissionEvidenceState.NOT_RUN}
    assert set(inventory.skill_states.values()) == {AdmissionEvidenceState.NOT_RUN}
    assert inventory.ready is False
    assert len(inventory.blockers) == 17 + len(expected_skill_ids)

    execution_plan = EvalExecutionPlanBuilder(store).build(
        inventory,
        scheduled_profile_ids=(),
    )
    assert execution_plan.execution_state == "NOT_RUN"
    assert execution_plan.execute is False
    assert execution_plan.blockers == ()
    assert len(execution_plan.items) == (17 * 9) + (29 * 5)
    assert len(execution_plan.items) == 298
