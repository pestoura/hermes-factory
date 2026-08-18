import json
from pathlib import Path

import yaml

from hermes_factory.agents import compile_profile_distribution


ROOT = Path(__file__).resolve().parents[2]


def test_all_admitted_profiles_compile_to_native_distribution(tmp_path):
    catalog = yaml.safe_load((ROOT / "agents/catalog-v1.2.yaml").read_text())["catalog"]
    registry = yaml.safe_load((ROOT / "skills/registry.yaml").read_text())
    active = catalog["active_candidates"]
    assert len(active) == 17

    for agent_id in active:
        agent_path = ROOT / "agents" / agent_id / "agent.yaml"
        soul_path = ROOT / "agents" / agent_id / "SOUL.md"
        assert agent_path.exists(), agent_id
        assert soul_path.exists(), agent_id
        out = tmp_path / agent_id
        compile_profile_distribution(
            yaml.safe_load(agent_path.read_text()),
            soul_path.read_text(),
            registry,
            out,
            cron_jobs=[],
        )
        assert yaml.safe_load((out / "distribution.yaml").read_text())["name"] == agent_id
        assert json.loads((out / "mcp.json").read_text()) == {}
        assert not (out / ".env").exists()
        assert not (out / "memories").exists()
        assert not (out / "sessions").exists()
