from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_inventory import (
    EvalInventoryBuilder,
    discover_skill_artifacts,
)
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.bindings import RuntimeComponentBinding
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder
from hermes_factory.traceability.registry import SemanticRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_phase_p_preflight_stays_blocked_with_current_eval_and_northbound_truth(tmp_path):
    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    registry_document = yaml.safe_load((ROOT / "skills/registry.yaml").read_text())
    runtime_policies = yaml.safe_load(
        (ROOT / "agents/_shared/runtime-policies.yaml").read_text()
    )
    skill_artifacts = discover_skill_artifacts(
        ROOT / "skills", registry_document["registry"]
    )

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
            runtime_policies=runtime_policies,
        )
        profile_artifacts[agent_id] = out

    store = EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))
    inventory = EvalInventoryBuilder(store).build(
        profile_artifacts=profile_artifacts,
        skill_artifacts=skill_artifacts,
        scheduled_profile_ids=(),
    )
    assert len(inventory.profile_states) == 17
    assert len(inventory.skill_states) == 29
    assert set(inventory.profile_states.values()) == {AdmissionEvidenceState.NOT_RUN}
    assert set(inventory.skill_states.values()) == {AdmissionEvidenceState.NOT_RUN}

    northbound_path = ROOT / "hermes-integration/mcp-bridge/factory-northbound.yaml"
    northbound = RuntimeComponentBinding.from_mapping(
        yaml.safe_load(northbound_path.read_text())
    )
    assert northbound.admission_state is AdmissionEvidenceState.BLOCKED

    # Isolate the known current blockers: all other Phase P component evidence
    # is treated as PASS in this integration test; northbound retains its
    # repository-declared external BLOCKED state.
    components = {component: AdmissionEvidenceState.PASS for component in RuntimeComponent}
    components[RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION] = northbound.admission_state

    plan = ControlledInstallPlanBuilder().build(
        # Synthetic matching SHAs intentionally isolate F/G + northbound blockers.
        # This test does not claim or infer the live accepted Hermes runtime SHA.
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        profile_artifacts=profile_artifacts,
        expected_profile_digests=inventory.profile_digests,
        profile_eval_states=inventory.profile_states,
        skill_eval_states=inventory.skill_states,
        component_states=components,
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=(
            ROOT / "hermes-integration/dashboard-plugin/hermes-factory"
        ),
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound_path,
    )

    assert plan.ready_for_controlled_execution is False
    assert plan.execute is False
    assert plan.execution_state == "BLOCKED"
    assert len(plan.blockers) == 17 + 29 + 1
    assert "Component NORTHBOUND_CONTROL_INTEGRATION=BLOCKED" in plan.blockers
    assert sum(blocker.startswith("Profile ") for blocker in plan.blockers) == 17
    assert sum(blocker.startswith("Skill ") for blocker in plan.blockers) == 29
