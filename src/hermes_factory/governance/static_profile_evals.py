from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from hermes_factory.agents.evals import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.agents.runtime_projection import project_native_profile_config

_EVALUATOR = "factory-static-profile-evaluator/v1"


def _canonical_skill(skill: str, aliases: dict[str, str]) -> str:
    if skill.startswith("factory-"):
        return skill
    return aliases.get(skill, skill)


def _state(passed: bool) -> ProfileEvalState:
    return ProfileEvalState.PASS if passed else ProfileEvalState.FAIL


class StaticProfileEvaluator:
    """Evaluate only mechanically decidable Profile admission dimensions.

    Behavioral dimensions such as routing, refusal behavior, handoff quality,
    escalation and independent review are intentionally outside this evaluator.
    """

    def evaluate(
        self,
        *,
        agent_document: dict[str, Any],
        profile_digest: str,
        distribution: Path,
        skill_registry: dict[str, Any],
        runtime_policies: dict[str, Any],
        evidence_ref: str,
    ) -> tuple[ProfileEvalEvidence, ...]:
        agent = agent_document.get("agent")
        if not isinstance(agent, dict):
            raise TypeError("agent document must contain agent mapping")
        profile_id = agent.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("agent.id is required")
        if not profile_digest.strip() or not evidence_ref.strip():
            raise ValueError("profile_digest and evidence_ref are required")

        expected_config = project_native_profile_config(agent, runtime_policies)
        actual_config = yaml.safe_load((distribution / "config.yaml").read_text(encoding="utf-8"))
        tool_policy_pass = actual_config == expected_config

        registry = skill_registry.get("registry", {})
        aliases_value = registry.get("legacy_source_aliases", {}) if isinstance(registry, dict) else {}
        aliases = {
            str(key): str(value)
            for key, value in aliases_value.items()
        } if isinstance(aliases_value, dict) else {}
        skills = agent.get("skills", {})
        required = skills.get("required", []) if isinstance(skills, dict) else []
        requested = {
            _canonical_skill(skill, aliases)
            for skill in required
            if isinstance(skill, str)
        }
        skills_root = distribution / "skills"
        projected = {
            entry.name
            for entry in skills_root.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        }
        skill_allowlist_pass = projected == requested

        tool_policy_class = agent.get("tool_policy_class")
        tool_policy_classes = runtime_policies.get("tool_policy_classes", {})
        policy = (
            tool_policy_classes.get(tool_policy_class)
            if isinstance(tool_policy_classes, dict) and isinstance(tool_policy_class, str)
            else None
        )
        mcp_policy_pass = isinstance(policy, dict) and policy.get("mcp") == []
        mcp_document = json.loads((distribution / "mcp.json").read_text(encoding="utf-8"))
        no_internal_mcp_pass = mcp_policy_pass and mcp_document == {}

        checks = (
            ("tool_policy_projection", tool_policy_pass),
            ("skill_allowlist", skill_allowlist_pass),
            ("no_internal_mcp_dependency", no_internal_mcp_pass),
        )
        return tuple(
            ProfileEvalEvidence(
                profile_id=profile_id,
                profile_digest=profile_digest,
                dimension=dimension,
                state=_state(passed),
                evidence_ref=f"{evidence_ref}#{dimension}",
                evaluator=_EVALUATOR,
            )
            for dimension, passed in checks
        )
