from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hermes_factory.contracts.project import AcceptanceContract, ProjectContract


class ProjectCompileError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalSourceRef:
    kind: str
    source_id: str
    revision: str
    digest: str

    def validate(self) -> None:
        for name, value in {
            "kind": self.kind,
            "source_id": self.source_id,
            "revision": self.revision,
            "digest": self.digest,
        }.items():
            if not value.strip():
                raise ProjectCompileError(f"canonical source {name} is required")


@dataclass(frozen=True)
class RepositorySnapshot:
    head_sha: str
    tests_digest: str
    ci_config_digest: str
    scm_state_digest: str


@dataclass(frozen=True)
class EcosystemSnapshot:
    snapshot_id: str
    digest: str
    capabilities: frozenset[str]


@dataclass(frozen=True)
class RequirementInput:
    requirement_id: str
    epic_id: str
    title: str
    depends_on: tuple[str, ...] = ()
    required_profiles: tuple[str, ...] = ()
    required_skills: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    security_sensitive: bool = False
    integration_required: bool = False
    fail_closed_review_required: bool = False
    hitl_boundaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompileInput:
    project: ProjectContract
    acceptance: AcceptanceContract
    requirements: tuple[RequirementInput, ...]
    jds_required_gates: tuple[str, ...]
    admitted_profiles: frozenset[str]
    admitted_skills: frozenset[str]
    canonical_sources: tuple[CanonicalSourceRef, ...] = ()
    repository_snapshot: RepositorySnapshot | None = None
    ecosystem_snapshot: EcosystemSnapshot | None = None
    board_state_revision: str = ""
    runtime_evidence_revision: str = ""
    factory_policy_revision: str = ""


@dataclass(frozen=True)
class EpicModel:
    epic_id: str
    requirement_ids: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceRequirement:
    kind: str
    requirement_id: str


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
    required_capabilities: tuple[str, ...] = ()
    hitl_boundaries: tuple[str, ...] = ()
    acceptance_requirements: tuple[AcceptanceRequirement, ...] = ()


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
        for canonical_source in source.canonical_sources:
            canonical_source.validate()

        ordered = _topological_requirements(source.requirements)
        gates = tuple(sorted(set(source.jds_required_gates)))
        ecosystem_capabilities = (
            source.ecosystem_snapshot.capabilities
            if source.ecosystem_snapshot is not None
            else frozenset()
        )

        work_packages: list[WorkPackageModel] = []
        gaps: list[CapabilityGap] = []
        for requirement in ordered:
            wp_id = f"WP-{requirement.requirement_id}"
            required_profiles = tuple(sorted(set(requirement.required_profiles)))
            required_skills = tuple(sorted(set(requirement.required_skills)))
            required_capabilities = tuple(sorted(set(requirement.required_capabilities)))
            stages = _workflow_stages(requirement, source.acceptance)
            work_packages.append(
                WorkPackageModel(
                    work_package_id=wp_id,
                    requirement_id=requirement.requirement_id,
                    epic_id=requirement.epic_id,
                    title=requirement.title,
                    depends_on=tuple(f"WP-{dep}" for dep in requirement.depends_on),
                    stages=stages,
                    required_profiles=required_profiles,
                    required_skills=required_skills,
                    jds_required_gates=gates,
                    required_capabilities=required_capabilities,
                    hitl_boundaries=tuple(sorted(set(requirement.hitl_boundaries))),
                    acceptance_requirements=_acceptance_requirements(
                        requirement,
                        source.acceptance,
                        gates,
                        stages,
                    ),
                )
            )
            for profile in required_profiles:
                if profile not in source.admitted_profiles:
                    gaps.append(CapabilityGap("PROFILE", profile, wp_id))
            for skill in required_skills:
                if skill not in source.admitted_skills:
                    gaps.append(CapabilityGap("SKILL", skill, wp_id))
            for capability in required_capabilities:
                if capability not in ecosystem_capabilities:
                    gaps.append(CapabilityGap("ECOSYSTEM_CAPABILITY", capability, wp_id))

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
    if requirement.fail_closed_review_required:
        stages.append("ADVERSARIAL_REVIEW")
    stages.extend(["REGRESSION", "CI", "EXACT_SHA", "MERGE"])
    if acceptance.runtime_required:
        stages.extend(["DEPLOY", "RUNTIME_VERIFY"])
    if acceptance.uat_required:
        stages.append("UAT")
    stages.extend(["OBSERVE", "ACCEPT"])
    return tuple(stages)


def _acceptance_requirements(
    requirement: RequirementInput,
    acceptance: AcceptanceContract,
    gates: tuple[str, ...],
    stages: tuple[str, ...],
) -> tuple[AcceptanceRequirement, ...]:
    requirements = [AcceptanceRequirement("JDS_GATE", gate) for gate in gates]
    requirements.append(AcceptanceRequirement("DETERMINISTIC_GATE", "EXACT_SHA"))
    if acceptance.uat_required:
        requirements.append(AcceptanceRequirement("UAT", "UAT"))
    if acceptance.runtime_required:
        requirements.append(AcceptanceRequirement("RUNTIME", "RUNTIME_VERIFY"))
    for stage in ("CODE_REVIEW", "SECURITY_REVIEW", "ADVERSARIAL_REVIEW"):
        if stage in stages:
            requirements.append(AcceptanceRequirement("INDEPENDENT_REVIEW", stage))
    return tuple(requirements)


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
                "required_capabilities": sorted(set(requirement.required_capabilities)),
                "security_sensitive": requirement.security_sensitive,
                "integration_required": requirement.integration_required,
                "fail_closed_review_required": requirement.fail_closed_review_required,
                "hitl_boundaries": sorted(set(requirement.hitl_boundaries)),
            }
            for requirement in ordered
        ],
        "jds_required_gates": list(gates),
        "admitted_profiles": sorted(source.admitted_profiles),
        "admitted_skills": sorted(source.admitted_skills),
        "canonical_sources": [
            {
                "kind": item.kind,
                "source_id": item.source_id,
                "revision": item.revision,
                "digest": item.digest,
            }
            for item in source.canonical_sources
        ],
        "repository_snapshot": (
            {
                "head_sha": source.repository_snapshot.head_sha,
                "tests_digest": source.repository_snapshot.tests_digest,
                "ci_config_digest": source.repository_snapshot.ci_config_digest,
                "scm_state_digest": source.repository_snapshot.scm_state_digest,
            }
            if source.repository_snapshot is not None
            else None
        ),
        "ecosystem_snapshot": (
            {
                "snapshot_id": source.ecosystem_snapshot.snapshot_id,
                "digest": source.ecosystem_snapshot.digest,
                "capabilities": sorted(source.ecosystem_snapshot.capabilities),
            }
            if source.ecosystem_snapshot is not None
            else None
        ),
        "board_state_revision": source.board_state_revision,
        "runtime_evidence_revision": source.runtime_evidence_revision,
        "factory_policy_revision": source.factory_policy_revision,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
