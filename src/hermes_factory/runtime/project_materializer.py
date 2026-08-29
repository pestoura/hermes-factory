from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hermes_factory.adapters.hermes_kanban import KanbanTaskProjection
from hermes_factory.compiler.project import ProjectModel, WorkPackageModel


class KanbanProjectionAdapter(Protocol):
    def ensure_board(self, **kwargs: object) -> dict[str, object]: ...

    def project_task(self, spec: KanbanTaskProjection) -> str: ...

    def retire_superseded_project_generations(
        self, **kwargs: str
    ) -> tuple[str, ...]: ...

    def authorize_dispatch(self, **kwargs: str) -> None: ...


@dataclass(frozen=True)
class StagePolicy:
    profile: str
    optional_skills: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MaterializedStageTask:
    work_package_id: str
    stage: str
    task_id: str


@dataclass(frozen=True)
class ProjectMaterialization:
    tasks: tuple[MaterializedStageTask, ...]

    def task_id(self, work_package_id: str, stage: str) -> str:
        for item in self.tasks:
            if item.work_package_id == work_package_id and item.stage == stage:
                return item.task_id
        raise KeyError(f"unknown materialized stage {work_package_id}/{stage}")


_STAGE_POLICIES: dict[str, StagePolicy] = {
    "DISCOVER": StagePolicy("factory-requirements-engineer"),
    "SPECIFY": StagePolicy("factory-requirements-engineer"),
    "DESIGN": StagePolicy("factory-software-architect"),
    "THREAT_MODEL": StagePolicy("factory-security-architect"),
    "TDD_RED": StagePolicy("factory-tdd-red"),
    "IMPLEMENT": StagePolicy(
        "factory-software-engineer",
        frozenset({
            "factory-implementing-python-changes",
            "factory-performing-root-cause-analysis",
        }),
    ),
    "UNIT": StagePolicy("factory-software-engineer"),
    "INTEGRATION": StagePolicy("factory-integration-tester"),
    "CODE_REVIEW": StagePolicy("factory-code-reviewer"),
    "SECURITY_REVIEW": StagePolicy("factory-security-reviewer"),
    "ADVERSARIAL_REVIEW": StagePolicy("factory-fail-closed-inspector"),
    "REGRESSION": StagePolicy("factory-integration-tester"),
    "CI": StagePolicy(
        "factory-platform-engineer",
        frozenset({"factory-performing-root-cause-analysis"}),
    ),
    "EXACT_SHA": StagePolicy("factory-release-manager"),
    "MERGE": StagePolicy("factory-release-manager"),
    "DEPLOY": StagePolicy(
        "factory-platform-engineer",
        frozenset({"factory-performing-root-cause-analysis"}),
    ),
    "RUNTIME_VERIFY": StagePolicy("factory-runtime-truth-observer"),
    "UAT": StagePolicy("factory-integration-tester"),
    "OBSERVE": StagePolicy("factory-runtime-truth-observer"),
    "ACCEPT": StagePolicy("factory-evidence-auditor"),
}

_CANDIDATE_BOUND_STAGES = frozenset(
    {
        "TDD_RED", "IMPLEMENT", "UNIT", "INTEGRATION", "CODE_REVIEW",
        "SECURITY_REVIEW", "ADVERSARIAL_REVIEW", "REGRESSION", "CI",
        "EXACT_SHA", "MERGE", "DEPLOY", "RUNTIME_VERIFY", "UAT",
        "OBSERVE", "ACCEPT",
    }
)
_REVIEW_STAGES = frozenset({"CODE_REVIEW", "SECURITY_REVIEW", "ADVERSARIAL_REVIEW"})
_STAGE_MUTATION_POLICIES = {
    "DISCOVER": "engineering_docs_only",
    "SPECIFY": "engineering_docs_only",
    "DESIGN": "engineering_docs_only",
    "THREAT_MODEL": "engineering_docs_only",
    "TDD_RED": "tests_and_docs_only",
    "IMPLEMENT": "implementation_no_tests",
    "UNIT": "tests_and_docs_only",
    "INTEGRATION": "tests_and_docs_only",
    "CODE_REVIEW": "evidence_docs_only",
    "SECURITY_REVIEW": "evidence_docs_only",
    "ADVERSARIAL_REVIEW": "evidence_docs_only",
    "REGRESSION": "tests_and_docs_only",
    "CI": "evidence_docs_only",
    "EXACT_SHA": "evidence_docs_only",
    "MERGE": "evidence_docs_only",
    "DEPLOY": "evidence_docs_only",
    "RUNTIME_VERIFY": "evidence_docs_only",
    "UAT": "evidence_docs_only",
    "OBSERVE": "evidence_docs_only",
    "ACCEPT": "evidence_docs_only",
}
_STAGE_CONTRACT_REVISION = "stage-contract-v13"


def stage_mutation_policy(stage: str) -> str:
    try:
        return _STAGE_MUTATION_POLICIES[stage]
    except KeyError as exc:
        raise ValueError(f"unknown Factory stage mutation policy: {stage}") from exc


def stage_artifact_root(work_package_id: str, stage: str) -> str:
    allowed = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    for name, value in (("work_package_id", work_package_id), ("stage", stage)):
        if not value or any(char not in allowed for char in value):
            raise ValueError(f"{name} is not safe for a Factory stage artifact path")
    return f"docs/factory/{work_package_id}/{stage}"


def _stage_mutation_instruction(stage: str) -> str:
    policy = stage_mutation_policy(stage)
    if policy in {"engineering_docs_only", "evidence_docs_only"}:
        return "This stage may commit engineering/evidence documentation only; production source changes are prohibited."
    if policy == "tests_and_docs_only":
        return "This stage may commit tests/fixtures and engineering documentation only; production source changes are prohibited."
    return "This stage may commit production implementation and engineering documentation; test changes are prohibited so prior RED evidence is not rewritten."


class ProjectMaterializer:
    """Project a compiled ProjectModel into native stage-level Kanban tasks."""

    def __init__(self, adapter: KanbanProjectionAdapter) -> None:
        self._adapter = adapter

    def materialize(
        self,
        model: ProjectModel,
        *,
        project_key: str,
        board: str,
        project_id: str,
        default_workdir: str,
        actor: str = "factory-orchestrator",
    ) -> ProjectMaterialization:
        self._validate(
            model,
            project_key=project_key,
            board=board,
            project_id=project_id,
            default_workdir=default_workdir,
        )
        ordered = _ordered_work_packages(model.work_packages)
        self._adapter.ensure_board(
            slug=board,
            name=project_key,
            description=f"Factory delivery board for {project_key}",
            default_workdir=default_workdir,
            project_id=project_id,
        )

        created: list[MaterializedStageTask] = []
        ids: dict[tuple[str, str], str] = {}
        root_task_ids: list[str] = []
        for wp in ordered:
            previous: str | None = None
            candidate_workspace: str | None = None
            candidate_branch = _candidate_branch(project_key, wp.work_package_id, model.digest)
            for index, stage in enumerate(wp.stages):
                parents: tuple[str, ...]
                if previous is not None:
                    parents = (previous,)
                elif wp.depends_on:
                    parents = tuple(ids[(dep, _final_stage(model, dep))] for dep in wp.depends_on)
                else:
                    parents = ()
                spec = self._projection(
                    model,
                    wp,
                    stage=stage,
                    board=board,
                    project_key=project_key,
                    project_id=project_id,
                    parents=parents,
                    priority=max(0, 100 - index),
                    workspace_path=candidate_workspace,
                    branch_name=candidate_branch,
                )
                task_id = self._adapter.project_task(spec)
                ids[(wp.work_package_id, stage)] = task_id
                created.append(MaterializedStageTask(wp.work_package_id, stage, task_id))
                previous = task_id
                if index == 0:
                    candidate_workspace = str(Path(default_workdir) / ".worktrees" / task_id)
                if not wp.depends_on and index == 0:
                    root_task_ids.append(task_id)

        self._adapter.retire_superseded_project_generations(
            board=board,
            project_key=project_key,
            keep_revision=f"{model.digest}.{_STAGE_CONTRACT_REVISION}",
            actor=actor,
            source="factory-project-materialization",
        )

        for task_id in root_task_ids:
            self._adapter.authorize_dispatch(
                board=board,
                task_id=task_id,
                actor=actor,
                source="factory-project-materialization",
            )
        return ProjectMaterialization(tuple(created))

    @staticmethod
    def _validate(
        model: ProjectModel,
        *,
        project_key: str,
        board: str,
        project_id: str,
        default_workdir: str,
    ) -> None:
        if model.capability_gaps:
            raise ValueError("project model has unresolved capability gaps")
        if not project_key.strip() or model.project_id != project_key:
            raise ValueError("project_key must match compiled project identity")
        if board != project_key:
            raise ValueError("Factory stages must materialize on the product board")
        if not project_id.strip() or not default_workdir.strip():
            raise ValueError("project_id and default_workdir are required")
        known_wps = {wp.work_package_id for wp in model.work_packages}
        for wp in model.work_packages:
            missing = set(wp.depends_on) - known_wps
            if missing:
                raise ValueError(f"unknown Work Package dependencies: {sorted(missing)}")
            for stage in wp.stages:
                if stage not in _STAGE_POLICIES:
                    raise ValueError(f"unknown Factory stage: {stage}")

    @staticmethod
    def _projection(
        model: ProjectModel,
        wp: WorkPackageModel,
        *,
        stage: str,
        board: str,
        project_key: str,
        project_id: str,
        parents: tuple[str, ...],
        priority: int,
        workspace_path: str | None,
        branch_name: str,
    ) -> KanbanTaskProjection:
        policy = _STAGE_POLICIES[stage]
        approved = tuple(
            sorted(set(wp.required_skills) & set(policy.optional_skills))
        )
        return KanbanTaskProjection(
            project_key=project_key,
            work_package_id=wp.work_package_id,
            stage=stage,
            revision=f"{model.digest}.{_STAGE_CONTRACT_REVISION}",
            title=f"{wp.work_package_id}/{stage}: {wp.title}",
            body=_task_body(model, wp, stage),
            assignee=policy.profile,
            approved_skills=approved,
            board=board,
            parent_task_ids=parents,
            priority=priority,
            workspace_kind="worktree",
            workspace_path=workspace_path,
            branch_name=branch_name,
            project_id=project_id,
        )


def _task_body(model: ProjectModel, wp: WorkPackageModel, stage: str) -> str:
    handoff = {
        "schema": "hermes.factory/handoff-completion/v1",
        "stage_outcome": "PASS|BLOCKED|UNKNOWN|NOT_RUN",
        "artifact_refs": ["artifact-or-source-ref"],
        "evidence_refs": ["evidence-ref"],
        "evidence_states": ["PASS"],
        "finding_state": "NONE|RESOLVED|OPEN",
        "context_revision": model.digest,
        "candidate_identity": "exact-sha-or-null",
        "independent_review_state": "PASS-or-null",
    }
    return "\n".join(
        (
            f"Factory stage: {stage}",
            f"Work Package: {wp.work_package_id}",
            f"Requirement: {wp.requirement_id}",
            f"Project model revision: {model.digest}",
            "Execute only this approved stage and preserve canonical project truth.",
            "The assigned worktree is the only local project-truth root for this stage.",
            "Do not search or read the parent repository root or sibling .worktrees.",
            "The canonical Git read boundary is current HEAD and its ancestors; do not enumerate or read refs, objects, reflogs, or superseded generations outside that reachable history.",
            "Use any path outside the assigned worktree only when it is an explicitly declared canonical external source.",
            "Do not invent or expand product scope. Optional improvements are DEFERRED_PROPOSAL, not HITL.",
            "Escalate only a real canonical conflict, authority boundary, security risk, or destructive operation.",
            "At completion, provide structured metadata.factory_handoff matching this contract:",
            json.dumps(handoff, sort_keys=True, separators=(",", ":")),
            "stage_outcome must be exactly PASS, BLOCKED, UNKNOWN, or NOT_RUN; promotion requires PASS.",
            "evidence_states must contain exactly one state for each evidence_refs entry, in the same order.",
            "Use finding_state=OPEN only for a real blocker that must prevent handoff; ordinary details assigned to the next approved stage are not OPEN findings.",
            "kanban_complete is permitted only for a handoff-ready PASS with finding_state NONE or RESOLVED and every evidence_state PASS.",
            "If a real blocker remains, do not complete the stage; use kanban_block with exact blocker evidence instead.",
            "If the blocker is a defect in the direct parent stage artifact, first restore the worktree to the last accepted candidate by removing only uncommitted changes created by this current stage.",
            "Then call kanban_block with kind=dependency and reason exactly: [factory:upstream-rework/v1] {\"producer_stage\":\"PARENT_STAGE\",\"finding\":\"bounded defect\",\"evidence_refs\":[\"repo/path\"]}.",
            "Do not use the upstream-rework protocol for external input, credentials, transient providers, or defects outside the direct parent stage.",
            "Before kanban_complete, commit stage-produced repository artifacts on the assigned branch using a bounded stage-specific commit; do not amend or rewrite prior commits.",
            "The worktree must be clean before kanban_complete; do not stage or commit unrelated pre-existing changes.",
            "If pre-existing unrelated changes make a clean stage checkpoint impossible, block the task rather than absorbing them.",
            "If this stage produces no repository changes, do not create an empty commit; preserve the clean existing HEAD.",
            "When candidate_identity is required, candidate_identity must equal the clean worktree HEAD after the stage checkpoint commit.",
            "If candidate_identity is supplied when optional, it must still equal the clean worktree HEAD and will be independently observed.",
            "factory_handoff metadata is runtime-only; never persist candidate_identity or other runtime handoff metadata inside stage-produced repository artifacts.",
            "After the final stage commit, observe the clean HEAD and pass that SHA directly to kanban_complete; do not modify the repository again.",
            f"repository_mutation_policy={stage_mutation_policy(stage)}",
            _stage_mutation_instruction(stage),
            f"stage_artifact_root={stage_artifact_root(wp.work_package_id, stage)}",
            "All stage-produced engineering/evidence documentation must be written only under stage_artifact_root; never pre-create another stage's artifacts.",
            "Engineering documentation completion requires at least one stage-owned repository artifact.",
            "candidate_identity_required=True",
            f"independent_review_required={stage in _REVIEW_STAGES}",
            "Worker completion prose alone is not Factory handoff proof.",
        )
    )


def _final_stage(model: ProjectModel, work_package_id: str) -> str:
    for wp in model.work_packages:
        if wp.work_package_id == work_package_id:
            if not wp.stages:
                raise ValueError(f"Work Package {work_package_id} has no stages")
            return wp.stages[-1]
    raise ValueError(f"unknown Work Package {work_package_id}")


def _ordered_work_packages(
    work_packages: tuple[WorkPackageModel, ...],
) -> tuple[WorkPackageModel, ...]:
    by_id = {wp.work_package_id: wp for wp in work_packages}
    remaining = {wp.work_package_id: set(wp.depends_on) for wp in work_packages}
    ordered: list[WorkPackageModel] = []
    while remaining:
        ready = sorted(
            wp_id for wp_id, deps in remaining.items() if not deps
        )
        if not ready:
            raise ValueError("Work Package dependency graph contains a cycle")
        for wp_id in ready:
            ordered.append(by_id[wp_id])
            remaining.pop(wp_id)
        completed = set(ready)
        for deps in remaining.values():
            deps.difference_update(completed)
    return tuple(ordered)


def _candidate_branch(project_key: str, work_package_id: str, revision: str) -> str:
    project = project_key.strip().lower()
    wp = work_package_id.strip().lower()
    return f"factory/{project}/{wp}-{revision[:12]}-{_STAGE_CONTRACT_REVISION}"
