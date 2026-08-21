import json
from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution
from hermes_factory.governance.eval_inventory import discover_skill_artifacts

ROOT = Path(__file__).resolve().parents[2]


def test_all_admitted_profiles_compile_to_native_distribution(tmp_path):
    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    registry = yaml.safe_load((ROOT / "skills/registry.yaml").read_text())
    runtime_policies = yaml.safe_load(
        (ROOT / "agents/_shared/runtime-policies.yaml").read_text()
    )
    skill_artifacts = discover_skill_artifacts(ROOT / "skills", registry["registry"])
    active = catalog["active_candidates"]
    assert len(active) == 17

    for agent_id in active:
        agent_path = ROOT / "agents" / agent_id / "agent.yaml"
        soul_path = ROOT / "agents" / agent_id / "SOUL.md"
        assert agent_path.exists(), agent_id
        assert soul_path.exists(), agent_id
        agent_document = yaml.safe_load(agent_path.read_text())
        out = tmp_path / agent_id
        compile_profile_distribution(
            agent_document,
            soul_path.read_text(),
            registry,
            out,
            cron_jobs=[],
            skill_artifacts=skill_artifacts,
            runtime_policies=runtime_policies,
        )
        assert yaml.safe_load((out / "distribution.yaml").read_text())["name"] == agent_id
        assert json.loads((out / "mcp.json").read_text()) == {}
        config = yaml.safe_load((out / "config.yaml").read_text())
        tool_policy_class = agent_document["agent"]["tool_policy_class"]
        assert config["toolsets"] == runtime_policies["tool_policy_classes"][tool_policy_class][
            "hermes_toolsets"
        ]
        assert config["terminal"]["home_mode"] == "profile"
        assert "model_class" not in config
        assert "tool_policy_class" not in config
        assert not list((out / "skills").glob("*.skillref"))
        assert not (out / ".env").exists()
        assert not (out / "memories").exists()
        assert not (out / "sessions").exists()
