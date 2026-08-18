import json
from pathlib import Path
from typing import Any

import yaml


class AgentCompileError(ValueError):
    pass


def _canonical_skill(skill: str, aliases: dict[str, str]) -> str:
    if skill.startswith("factory-"):
        return skill
    return aliases.get(skill, skill)


def compile_profile_distribution(
    agent_document: dict[str, Any],
    soul: str,
    skill_registry: dict[str, Any],
    destination: Path,
    *,
    cron_jobs: list[dict[str, Any]],
) -> Path:
    agent = agent_document.get("agent")
    if not isinstance(agent, dict):
        raise AgentCompileError("agent document must contain agent mapping")
    agent_id = agent.get("id")
    if not isinstance(agent_id, str) or not agent_id:
        raise AgentCompileError("agent.id is required")

    registry = skill_registry.get("registry", {})
    aliases = registry.get("legacy_source_aliases", {})
    consumer = registry.get("consumers", {}).get(agent_id)
    if not isinstance(consumer, dict):
        raise AgentCompileError(f"no Skill consumer policy for {agent_id}")
    admitted = set(consumer.get("required", [])) | set(consumer.get("task_optional", []))
    requested = [
        _canonical_skill(skill, aliases)
        for skill in agent.get("skills", {}).get("required", [])
    ]
    not_admitted = sorted(set(requested) - admitted)
    if not_admitted:
        raise AgentCompileError(f"Skill(s) not admitted for {agent_id}: {not_admitted}")

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "skills").mkdir(exist_ok=True)
    (destination / "cron").mkdir(exist_ok=True)

    manifest = {
        "name": agent_id,
        "version": str(agent.get("version", "0.0.0")),
        "description": str(agent.get("description", "")),
        # Hermes 0.20.x currently accepts one comparator in hermes_requires.
        # Keep the native manifest installable instead of emitting a
        # comma-separated range that its semver parser cannot consume.
        "hermes_requires": ">=0.20.0",
        "author": "Hermes Software Factory",
        "distribution_owned": [
            "SOUL.md",
            "config.yaml",
            "mcp.json",
            "skills/",
            "cron/",
            "distribution.yaml",
        ],
    }
    (destination / "distribution.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (destination / "SOUL.md").write_text(soul)
    config = {
        "model_class": agent.get("model_class"),
        "tool_policy_class": agent.get("tool_policy_class"),
        "factory_agent_id": agent_id,
    }
    (destination / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (destination / "mcp.json").write_text(json.dumps({}, indent=2) + "\n")
    for skill in requested:
        (destination / "skills" / f"{skill}.skillref").write_text(skill + "\n")
    for job in cron_jobs:
        job_id = job.get("id")
        if not isinstance(job_id, str) or not job_id or "/" in job_id:
            raise AgentCompileError("cron job id must be a safe non-empty string")
        (destination / "cron" / f"{job_id}.json").write_text(
            json.dumps(job, sort_keys=True, indent=2) + "\n"
        )
    return destination
