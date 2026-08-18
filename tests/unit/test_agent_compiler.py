import json
from pathlib import Path

import pytest
import yaml

from hermes_factory.agents import compile_profile_distribution


def test_agent_compiles_to_native_hermes_distribution_without_internal_mcp(tmp_path: Path):
    agent = {
        "agent": {
            "id": "factory-code-reviewer",
            "version": "1.0.0",
            "description": "Independent reviewer",
            "model_class": "reasoning-high",
            "tool_policy_class": "review",
            "skills": {"required": ["reading-project-truth", "reviewing-code-independently"]},
        }
    }
    registry = {
        "registry": {
            "legacy_source_aliases": {
                "reading-project-truth": "factory-reading-project-truth",
                "reviewing-code-independently": "factory-reviewing-code-independently",
            },
            "consumers": {
                "factory-code-reviewer": {
                    "required": [
                        "factory-reading-project-truth",
                        "factory-reviewing-code-independently",
                    ]
                }
            },
        }
    }
    out = tmp_path / "profile"
    compile_profile_distribution(agent, "# Reviewer Soul\n", registry, out, cron_jobs=[])
    manifest = yaml.safe_load((out / "distribution.yaml").read_text())
    assert manifest["name"] == "factory-code-reviewer"
    assert manifest["hermes_requires"] == ">=0.20.0,<0.21.0"
    assert json.loads((out / "mcp.json").read_text()) == {}
    assert yaml.safe_load((out / "config.yaml").read_text())["tool_policy_class"] == "review"
    assert (out / "skills" / "factory-reading-project-truth.skillref").exists()
    assert (out / "skills" / "factory-reviewing-code-independently.skillref").exists()


def test_agent_compiler_projects_cron_only_inside_distribution(tmp_path: Path):
    agent = {
        "agent": {
            "id": "factory-orchestrator",
            "version": "1.0.0",
            "description": "Control",
            "model_class": "reasoning-high",
            "tool_policy_class": "control-orchestrate",
            "skills": {"required": []},
        }
    }
    registry = {
        "registry": {
            "legacy_source_aliases": {},
            "consumers": {"factory-orchestrator": {"required": []}},
        }
    }
    out = tmp_path / "profile"
    compile_profile_distribution(
        agent,
        "# Soul\n",
        registry,
        out,
        cron_jobs=[
            {"id": "reconcile", "schedule": "0 * * * *", "prompt": "Reconcile projects"}
        ],
    )
    assert (out / "cron" / "reconcile.json").exists()
    assert not (out / "systemd").exists()
    assert not (out / "crontab").exists()


def test_compiler_fails_if_agent_declares_skill_not_admitted_for_consumer(tmp_path: Path):
    agent = {
        "agent": {
            "id": "factory-code-reviewer",
            "version": "1.0.0",
            "description": "Review",
            "model_class": "reasoning-high",
            "tool_policy_class": "review",
            "skills": {"required": ["reading-project-truth"]},
        }
    }
    registry = {
        "registry": {
            "legacy_source_aliases": {
                "reading-project-truth": "factory-reading-project-truth"
            },
            "consumers": {"factory-code-reviewer": {"required": []}},
        }
    }
    with pytest.raises(ValueError, match="not admitted"):
        compile_profile_distribution(agent, "# Soul\n", registry, tmp_path / "x", cron_jobs=[])
