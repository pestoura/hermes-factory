from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class SkillAdmissionError(ValueError):
    pass


@dataclass(frozen=True)
class SkillAdmission:
    skill_id: str
    version: str
    lifecycle: str


@dataclass(frozen=True)
class SkillEvalRecord:
    baseline_red: bool
    skill_green: bool
    variation_eval: bool
    pressure_eval: bool
    independent_review: bool

    @property
    def promotable(self) -> bool:
        return all((self.baseline_red, self.skill_green, self.variation_eval,
                    self.pressure_eval, self.independent_review))

    def require_active(self, skill_id: str) -> SkillAdmission:
        if not self.promotable:
            raise SkillAdmissionError(f"{skill_id} cannot be ACTIVE before all evaluations PASS")
        return SkillAdmission(skill_id, "1.0.0", "ACTIVE")


_CATEGORIES = ("core", "control_workforce", "product_architecture", "documentation",
               "engineering_quality", "security_assurance", "governance_operations")


class SkillRegistry:
    def __init__(self, *, aliases: dict[str, str], registered: frozenset[str],
                 consumers: dict[str, dict[str, tuple[str, ...]]]) -> None:
        self._aliases = aliases
        self._registered = registered
        self._consumers = consumers

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "SkillRegistry":
        if document.get("schema") != "hermes.factory/skills/v1.2":
            raise SkillAdmissionError("unsupported Skill Registry schema")
        raw = document.get("registry")
        if not isinstance(raw, dict):
            raise SkillAdmissionError("registry mapping is required")

        registered: set[str] = set()
        for category in _CATEGORIES:
            values = raw.get(category, [])
            if not isinstance(values, list):
                raise SkillAdmissionError(f"registry.{category} must be a list")
            for value in values:
                if not isinstance(value, str) or not value.startswith("factory-"):
                    raise SkillAdmissionError(f"registry.{category} entries must be canonical factory-* ids")
                registered.add(value)
        proposed = raw.get("proposed_v1_2_skills", {})
        if not isinstance(proposed, dict):
            raise SkillAdmissionError("proposed_v1_2_skills must be a mapping")
        for skill_id in proposed:
            if not isinstance(skill_id, str) or not skill_id.startswith("factory-"):
                raise SkillAdmissionError("proposed Skill ids must be canonical factory-* ids")
            registered.add(skill_id)

        aliases_raw = raw.get("legacy_source_aliases", {})
        if not isinstance(aliases_raw, dict):
            raise SkillAdmissionError("legacy_source_aliases must be a mapping")
        aliases: dict[str, str] = {}
        for source_id, target_id in aliases_raw.items():
            if not isinstance(source_id, str) or not isinstance(target_id, str):
                raise SkillAdmissionError("Skill aliases must be strings")
            if not target_id.startswith("factory-") or target_id not in registered:
                raise SkillAdmissionError(f"Skill alias target {target_id} is not registered canonical identity")
            aliases[source_id] = target_id

        consumers_raw = raw.get("consumers", {})
        if not isinstance(consumers_raw, dict):
            raise SkillAdmissionError("consumers must be a mapping")
        consumers: dict[str, dict[str, tuple[str, ...]]] = {}
        for agent_id, policy in consumers_raw.items():
            if not isinstance(agent_id, str) or not isinstance(policy, dict):
                raise SkillAdmissionError("invalid Skill consumer policy")
            parsed: dict[str, tuple[str, ...]] = {}
            for key in ("required", "task_optional"):
                values = policy.get(key, [])
                if not isinstance(values, list):
                    raise SkillAdmissionError(f"consumer {agent_id}.{key} must be a list")
                result: list[str] = []
                for skill_id in values:
                    if not isinstance(skill_id, str):
                        raise SkillAdmissionError(f"consumer {agent_id}.{key} has invalid id")
                    canonical = aliases.get(skill_id, skill_id)
                    if canonical not in registered:
                        raise SkillAdmissionError(f"consumer {agent_id} references Skill {canonical} not registered")
                    result.append(canonical)
                parsed[key] = tuple(result)
            consumers[agent_id] = parsed
        return cls(aliases=aliases, registered=frozenset(registered), consumers=consumers)

    def resolve(self, skill_id: str) -> str:
        canonical = self._aliases.get(skill_id, skill_id)
        if canonical not in self._registered:
            raise SkillAdmissionError(f"Skill {skill_id} is not registered")
        return canonical

    def effective_skills(self, agent_id: str, *, task_approved: tuple[str, ...],
                         admitted: frozenset[str]) -> tuple[str, ...]:
        consumer = self._consumers.get(agent_id)
        if consumer is None:
            raise SkillAdmissionError(f"no Skill consumer policy for {agent_id}")
        required = set(consumer["required"])
        allowed = required | set(consumer["task_optional"])
        requested: set[str] = set()
        for raw_skill in task_approved:
            try:
                canonical = self.resolve(raw_skill)
            except SkillAdmissionError as exc:
                raise SkillAdmissionError(f"Skill {raw_skill} is not authorized for {agent_id}") from exc
            if canonical not in allowed:
                raise SkillAdmissionError(f"Skill {canonical} is not authorized for {agent_id}")
            requested.add(canonical)
        effective = required | requested
        missing = sorted(effective - set(admitted))
        if missing:
            raise SkillAdmissionError(f"Skill(s) not admitted: {missing}")
        return tuple(sorted(effective))


def compile_native_skill(source: Path, *, source_id: str, registry: SkillRegistry,
                         destination: Path, origin_repo: str, origin_ref: str) -> Path:
    canonical = registry.resolve(source_id)
    text = source.read_text()
    if not text.startswith("---\n"):
        raise SkillAdmissionError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SkillAdmissionError("SKILL.md frontmatter is not terminated")
    frontmatter = yaml.safe_load(text[4:end])
    body = text[end + 5:]
    if not isinstance(frontmatter, dict):
        raise SkillAdmissionError("SKILL.md frontmatter must be a mapping")
    name = frontmatter.get("name")
    if not isinstance(name, str) or registry.resolve(name) != canonical:
        raise SkillAdmissionError("SKILL.md name does not match source identity")
    frontmatter["name"] = canonical
    metadata = frontmatter.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise SkillAdmissionError("SKILL.md metadata must be a mapping")
    factory = metadata.setdefault("factory", {})
    if not isinstance(factory, dict):
        raise SkillAdmissionError("SKILL.md metadata.factory must be a mapping")
    factory.update({"managed_by": "hermes-factory", "origin_repo": origin_repo, "origin_ref": origin_ref})
    target = destination / canonical / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\n" + yaml.safe_dump(frontmatter, sort_keys=False).rstrip() + "\n---\n" + body)
    return target
