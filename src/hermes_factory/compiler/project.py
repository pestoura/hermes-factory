from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hermes_factory.contracts.project import AcceptanceContract, ProjectContract


class ProjectCompileError(ValueError):
    pass


@dataclass(frozen=True)
class RequirementInput:
    requirement_id: str
    epic_id: str
    title: str
    depends_on: tuple[str, ...] = ()
    required_profiles: tuple[str, ...] = ()
    required_skills: tuple[str, ...] = ()
    security_sensitive: bool = False
    integration_required: bool = False


@dataclass(frozen=True)
class CompileInput:
    project: ProjectContract
    acceptance: AcceptanceContract
    requirements: tuple[RequirementInput, ...]
    jds_required_gates: tuple[str, ...]
    admitted_profiles: frozenset[str]
    admitted_skills: frozenset[str]


@dataclass(frozen=True)
class EpicModel:
    epic_id: str
    requirement_ids: tuple[str, ...]


@dataclass(frozen=True)
class WorkPackageModel:
    work_package_id: str
    requirement_id: str
    epic_id: str
    title: str
    depends_on: tuple[str, ...]
    stages: tuple[str, ...]
    required_profiles: tuple[str, ...]
    required_skills: tuple[str, ...]
    jds_required_gates: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityGap:
    kind: str
    capability_id: str
    work_package_id: str


@dataclass(frozen=True)
class ProjectModel:
    project_id: str
    digest: str
    epics: tuple[EpicModel, ...]
    work_packages: tuple[WorkPackageModel, ...]
    capability_gaps: tuple[CapabilityGap, ...]
    jds_required_gates: tuple[str, ...]
    owner_acceptance_required: bool


class ProjectCompiler:
    """Compile approved semantic inputs into a deterministic delivery model.

    JDS gate decisions are consumed as immutable input. This compiler preserves
    them and adds Factory workflow semantics; it does not decide generic JDS
    engineering controls itself.
    """

    def compile(self, source: CompileInput) -> ProjectModel:
        ordered = _topological_requirements(source.requirements)
        gates = tuple(sorted(set(source.jds_required_gates)))

        work_packages: list[WorkPackageModel] = []
        gaps: list[CapabilityGap] = []
        for requirement in ordered:
            wp_id = f"WP-{requirement.requirement_id}"
            required_profiles = tuple(sorted(set(requirement.required_profiles)))
            required_skills = tuple(sorted(set(requirement.required_skills)))
            work_packages.append(
                WorkPackageModel(
                    work_package_id=wp_id,
                    requirement_id=requirement.requirement_id,
                    epic_id=requirement.epic_id,
                    title=requirement.title,
                    depends_on=tuple(f"WP-{dep}" for dep in requirement.depends_on),
                    stages=_workflow_stages(requirement, source.acceptance),
                    required_profiles=required_profiles,
                    required_skills=required_skills,
                    jds_required_gates=gates,
                )
            )
            for profile in required_profiles:
                if profile not in source.admitted_profiles:
                    gaps.append(CapabilityGap("PROFILE", profile, wp_id))
            for skill in required_skills:
                if skill not in source.admitted_skills:
                    gaps.append(CapabilityGap("SKILL", skill, wp_id))

        epic_map: dict[str, list[str]] = {}
        for requirement in ordered:
            epic_map.setdefault(requirement.epic_id, []).append(requirement.requirement_id)
        epics = tuple(
            EpicModel(epic_id, tuple(requirement_ids))
            for epic_id, requirement_ids in sorted(epic_map.items())
        )

        return ProjectModel(
            project_id=source.project.project_id,
            digest=_digest(source, ordered, gates),
            epics=epics,
            work_packages=tuple(work_packages),
            capability_gaps=tuple(
                sorted(gaps, key=lambda gap: (gap.work_package_id, gap.kind, gap.capability_id))
            ),
            jds_required_gates=gates,
            owner_acceptance_required=source.acceptance.owner_acceptance_required,
        )


def _workflow_stages(
    requirement: RequirementInput,
    acceptance: AcceptanceContract,
) -> tuple[str, ...]:
    stages = ["DISCOVER", "SPECIFY", "DESIGN"]
    if requirement.security_sensitive:
        stages.append("THREAT_MODEL")
    stages.extend(["TDD_RED", "IMPLEMENT", "UNIT"])
    if requirement.integration_required:
        stages.append("INTEGRATION")
    stages.append("CODE_REVIEW")
    if requirement.security_sensitive:
        stages.append("SECURITY_REVIEW")
    stages.extend(["REGRESSION", "CI", "EXACT_SHA", "MERGE"])
    if acceptance.runtime_required:
        stages.extend(["DEPLOY", "RUNTIME_VERIFY"])
    if acceptance.uat_required:
        stages.append("UAT")
    stages.extend(["OBSERVE", "ACCEPT"])
    return tuple(stages)


def _topological_requirements(
    requirements: tuple[RequirementInput, ...],
) -> tuple[RequirementInput, ...]:
    by_id: dict[str, RequirementInput] = {}
    positions: dict[str, int] = {}
    for position, requirement in enumerate(requirements):
        if not requirement.requirement_id.strip():
            raise ProjectCompileError("requirement_id is required")
        if requirement.requirement_id in by_id:
            raise ProjectCompileError(f"duplicate requirement {requirement.requirement_id}")
        by_id[requirement.requirement_id] = requirement
        positions[requirement.requirement_id] = position

    for requirement in requirements:
        for dependency in requirement.depends_on:
            if dependency not in by_id:
                raise ProjectCompileError(
                    f"unknown dependency {dependency} for {requirement.requirement_id}"
                )

    indegree = {requirement_id: 0 for requirement_id in by_id}
    children: dict[str, list[str]] = {requirement_id: [] for requirement_id in by_id}
    for requirement in requirements:
        for dependency in requirement.depends_on:
            indegree[requirement.requirement_id] += 1
            children[dependency].append(requirement.requirement_id)

    ready = sorted(
        (requirement_id for requirement_id, count in indegree.items() if count == 0),
        key=lambda requirement_id: (positions[requirement_id], requirement_id),
    )
    ordered: list[RequirementInput] = []
    while ready:
        requirement_id = ready.pop(0)
        ordered.append(by_id[requirement_id])
        for child in sorted(
            children[requirement_id],
            key=lambda item: (positions[item], item),
        ):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda item: (positions[item], item))

    if len(ordered) != len(requirements):
        raise ProjectCompileError("requirement dependency cycle detected")
    return tuple(ordered)


def _digest(
    source: CompileInput,
    ordered: tuple[RequirementInput, ...],
    gates: tuple[str, ...],
) -> str:
    payload = {
        "project": {
            "id": source.project.project_id,
            "name": source.project.name,
            "repository": source.project.repository,
            "autonomy": source.project.autonomy,
        },
        "acceptance": {
            "uat_required": source.acceptance.uat_required,
            "runtime_required": source.acceptance.runtime_required,
            "owner_acceptance_required": source.acceptance.owner_acceptance_required,
        },
        "requirements": [
            {
                "id": requirement.requirement_id,
                "epic": requirement.epic_id,
                "title": requirement.title,
                "depends_on": list(requirement.depends_on),
                "required_profiles": sorted(set(requirement.required_profiles)),
                "required_skills": sorted(set(requirement.required_skills)),
                "security_sensitive": requirement.security_sensitive,
                "integration_required": requirement.integration_required,
            }
            for requirement in ordered
        ],
        "jds_required_gates": list(gates),
        "admitted_profiles": sorted(source.admitted_profiles),
        "admitted_skills": sorted(source.admitted_skills),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
