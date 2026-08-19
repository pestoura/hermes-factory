import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from hermes_factory.agents.runtime_projection import project_native_profile_config
from hermes_factory.skills.artifacts import compile_skill_artifact


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
    skill_artifacts: Mapping[str, Path] | None = None,
    runtime_policies: dict[str, Any],
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

    artifact_map = skill_artifacts or {}
    missing_artifacts = sorted(set(requested) - set(artifact_map))
    if missing_artifacts:
        raise AgentCompileError(
            f"canonical Skill artifact(s) missing for {agent_id}: {missing_artifacts}"
        )

    destination.mkdir(parents=True, exist_ok=True)
    skills_destination = destination / "skills"
    skills_destination.mkdir(exist_ok=True)
    (destination / "cron").mkdir(exist_ok=True)

    manifest = {
        "name": agent_id,
        "version": str(agent.get("version", "0.0.0")),
        "description": str(agent.get("description", "")),
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
    config = project_native_profile_config(agent, runtime_policies)
    (destination / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (destination / "mcp.json").write_text(json.dumps({}, indent=2) + "\n")
    for skill in requested:
        compile_skill_artifact(
            artifact_map[skill],
            canonical_id=skill,
            destination_root=skills_destination,
        )

    # Runtime cron state is deliberately not manufactured at build-time.
    # Phase P materializes validated duties through the native Hermes cron
    # primitive after the Profile has been installed.
    for job in cron_jobs:
        job_id = job.get("id")
        if not isinstance(job_id, str) or not job_id or "/" in job_id:
            raise AgentCompileError("cron job id must be a safe non-empty string")

    return destination
