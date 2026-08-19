import json
from pathlib import Path

import pytest
import yaml

from hermes_factory.agents import compile_profile_distribution


def _skill_source(tmp_path: Path, name: str) -> Path:
    source = tmp_path / "skill-sources" / name
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test Skill\nversion: 0.1.0\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return source


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
    skill_artifacts = {
        "factory-reading-project-truth": _skill_source(tmp_path, "reading-project-truth"),
        "factory-reviewing-code-independently": _skill_source(
            tmp_path, "reviewing-code-independently"
        ),
    }
    out = tmp_path / "profile"
    compile_profile_distribution(
        agent,
        "# Reviewer Soul\n",
        registry,
        out,
        cron_jobs=[],
        skill_artifacts=skill_artifacts,
    )
    manifest = yaml.safe_load((out / "distribution.yaml").read_text())
    assert manifest["name"] == "factory-code-reviewer"
    # Hermes 0.20.x profile_distribution.check_hermes_requires accepts one
    # comparator only; comma-separated ranges are not a supported manifest
    # contract and fail native semver parsing.
    assert manifest["hermes_requires"] == ">=0.20.0"
    assert json.loads((out / "mcp.json").read_text()) == {}
    assert yaml.safe_load((out / "config.yaml").read_text())["tool_policy_class"] == "review"
    first = out / "skills" / "factory-reading-project-truth" / "SKILL.md"
    second = out / "skills" / "factory-reviewing-code-independently" / "SKILL.md"
    assert first.is_file()
    assert second.is_file()
    assert yaml.safe_load(first.read_text().split("---", 2)[1])["name"] == (
        "factory-reading-project-truth"
    )
    assert yaml.safe_load(second.read_text().split("---", 2)[1])["name"] == (
        "factory-reviewing-code-independently"
    )
    assert not list((out / "skills").glob("*.skillref"))


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
        skill_artifacts={},
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
        compile_profile_distribution(
            agent,
            "# Soul\n",
            registry,
            tmp_path / "x",
            cron_jobs=[],
            skill_artifacts={},
        )
