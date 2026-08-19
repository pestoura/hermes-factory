from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_inventory import EvalInventoryBuilder
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
    aliases = registry["legacy_source_aliases"]

    profile_artifacts = {}
    for agent_id in catalog["active_candidates"]:
        out = tmp_path / "profiles" / agent_id
        compile_profile_distribution(
            yaml.safe_load((ROOT / "agents" / agent_id / "agent.yaml").read_text()),
            (ROOT / "agents" / agent_id / "SOUL.md").read_text(),
            registry_document,
            out,
            cron_jobs=[],
        )
        profile_artifacts[agent_id] = out

    expected_skill_ids = {
        skill_id
        for group in _SKILL_GROUPS
        for skill_id in registry[group]
    }
    skill_artifacts = {}
    for skill_file in sorted(ROOT.glob("skills/*/*/SKILL.md")):
        source_name = skill_file.parent.name
        canonical_id = aliases.get(source_name, f"factory-{source_name}")
        assert canonical_id not in skill_artifacts, canonical_id
        skill_artifacts[canonical_id] = skill_file

    assert len(profile_artifacts) == 17
    assert set(skill_artifacts) == expected_skill_ids
    assert set(registry["proposed_v1_2_skills"]) <= expected_skill_ids

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
