from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Mapping, Protocol

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.hermes_install_runtime import CommandRunner
from hermes_factory.skills.artifacts import compile_skill_artifact
from hermes_factory.skills.system import SkillRegistry


class NativeTask(Protocol):
    assignee: str
    skills: tuple[str, ...]
    workspace_kind: str


class NativeTaskRuntime(Protocol):
    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...

    def get_task(self, conn: object, task_id: str) -> NativeTask | None: ...

    def resolve_workspace(self, task: NativeTask, *, board: str) -> str: ...


class HermesTaskSkillPreparer:
    """Project only task-approved optional Skills into a native task worktree.

    Required Factory Skills remain Profile-owned. Optional Skills are admitted
    again from the canonical Factory Skill Registry, content-addressed against
    their expected source digest, copied into the task worktree's native
    ``.hermes/skills`` surface, and the exact worktree is trusted for the
    assignee Profile before dispatch may be released.
    """

    def __init__(
        self,
        *,
        native: NativeTaskRuntime,
        skill_registry: SkillRegistry,
        admitted_skill_ids: frozenset[str],
        skill_sources: Mapping[str, Path],
        expected_skill_digests: Mapping[str, str],
        command_runner: CommandRunner,
    ) -> None:
        self._native = native
        self._registry = skill_registry
        self._admitted = admitted_skill_ids
        self._skill_sources = {key: Path(value) for key, value in skill_sources.items()}
        self._expected_digests = dict(expected_skill_digests)
        self._runner = command_runner

    @staticmethod
    def _require_text(value: str, field: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field} is required")
        return normalized

    def _load_task(self, *, board: str, task_id: str) -> NativeTask:
        with self._native.connect_closing(board=board) as conn:
            task = self._native.get_task(conn, task_id)
        if task is None:
            raise RuntimeError(f"native Hermes task {task_id} does not exist")
        if not isinstance(task.assignee, str) or not task.assignee.strip():
            raise RuntimeError("native Hermes task assignee is required")
        if not isinstance(task.skills, tuple) or not all(
            isinstance(skill, str) and skill.strip() for skill in task.skills
        ):
            raise RuntimeError("native Hermes task Skills must be explicit strings")
        if not isinstance(task.workspace_kind, str):
            raise RuntimeError("native Hermes task workspace kind is invalid")
        return task

    def _optional_skills(self, task: NativeTask) -> tuple[str, ...]:
        required = self._registry.effective_skills(
            task.assignee,
            task_approved=(),
            admitted=self._admitted,
        )
        effective = self._registry.effective_skills(
            task.assignee,
            task_approved=task.skills,
            admitted=self._admitted,
        )
        actual = tuple(sorted(set(task.skills)))
        if actual != effective:
            raise RuntimeError(
                "native Hermes task Skill set does not match Factory authorization"
            )
        return tuple(sorted(set(effective) - set(required)))

    def _verify_sources(self, optional_skills: tuple[str, ...]) -> None:
        for skill_id in optional_skills:
            source = self._skill_sources.get(skill_id)
            expected = self._expected_digests.get(skill_id)
            if source is None or expected is None:
                raise RuntimeError(f"task Skill source identity missing for {skill_id}")
            observed = digest_artifact(source)
            if observed != expected:
                raise RuntimeError(
                    f"task Skill source digest mismatch for {skill_id}: "
                    f"expected {expected}, observed {observed}"
                )

    @staticmethod
    def _safe_skills_root(workspace: Path) -> Path:
        hermes_dir = workspace / ".hermes"
        skills_root = hermes_dir / "skills"
        for path, label in ((hermes_dir, ".hermes"), (skills_root, ".hermes/skills")):
            if path.exists() and (path.is_symlink() or not path.is_dir()):
                raise RuntimeError(f"task worktree {label} must be a regular directory")
        hermes_dir.mkdir(exist_ok=True)
        skills_root.mkdir(exist_ok=True)
        return skills_root

    def _project_optional_skills(
        self,
        *,
        workspace: Path,
        optional_skills: tuple[str, ...],
    ) -> list[Path]:
        skills_root = self._safe_skills_root(workspace)
        created: list[Path] = []
        with tempfile.TemporaryDirectory(
            prefix=".factory-skill-stage-",
            dir=str(workspace),
        ) as stage_dir:
            stage_root = Path(stage_dir)
            for skill_id in optional_skills:
                source = self._skill_sources[skill_id]
                staged = compile_skill_artifact(
                    source,
                    canonical_id=skill_id,
                    destination_root=stage_root,
                )
                staged_digest = digest_artifact(staged)
                target = skills_root / skill_id
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or not target.is_dir():
                        raise RuntimeError(f"task Skill target collision for {skill_id}")
                    if digest_artifact(target) != staged_digest:
                        raise RuntimeError(f"task Skill target collision for {skill_id}")
                    continue
                staged.replace(target)
                created.append(target)
        return created

    def _run(self, argv: tuple[str, ...], label: str) -> str:
        result = self._runner.run(argv)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        return result.stdout

    def _untrust(self, *, profile: str, workspace: Path) -> None:
        result = self._runner.run(
            (
                "hermes",
                "-p",
                profile,
                "skills",
                "untrust",
                str(workspace),
            )
        )
        if result.returncode != 0:
            raise RuntimeError(
                "task Skill trust compensation failed; runtime trust state is unknown"
            )

    @staticmethod
    def _cleanup(created: list[Path]) -> None:
        for target in reversed(created):
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target)

    def _trust_workspace(self, *, profile: str, workspace: Path, created: list[Path]) -> None:
        trust_attempted = False
        try:
            trust_attempted = True
            self._run(
                (
                    "hermes",
                    "-p",
                    profile,
                    "skills",
                    "trust",
                    str(workspace),
                ),
                "task Skill worktree trust",
            )
            raw = self._run(
                (
                    "hermes",
                    "-p",
                    profile,
                    "config",
                    "get",
                    "skills.trusted_project_dirs",
                    "--json",
                ),
                "task Skill trust verification",
            )
            try:
                trusted = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("task Skill trust verification returned invalid JSON") from exc
            if not isinstance(trusted, list) or str(workspace) not in trusted:
                raise RuntimeError("task Skill trust verification failed")
        except Exception as exc:
            compensation_error: Exception | None = None
            if trust_attempted:
                try:
                    self._untrust(profile=profile, workspace=workspace)
                except Exception as rollback_exc:
                    compensation_error = rollback_exc
            self._cleanup(created)
            if compensation_error is not None:
                raise RuntimeError(str(compensation_error)) from exc
            raise

    def prepare(self, *, board: str, task_id: str) -> None:
        board = self._require_text(board, "board")
        task_id = self._require_text(task_id, "task_id")
        task = self._load_task(board=board, task_id=task_id)
        optional_skills = self._optional_skills(task)
        if not optional_skills:
            return
        if task.workspace_kind != "worktree":
            raise RuntimeError("task-approved optional Factory Skills require a worktree")

        # Validate every source identity before materializing any task workspace.
        self._verify_sources(optional_skills)

        raw_workspace = Path(self._native.resolve_workspace(task, board=board))
        if raw_workspace.is_symlink() or not raw_workspace.is_dir():
            raise RuntimeError("native Hermes task worktree must be a regular directory")
        workspace = raw_workspace.resolve()
        created = self._project_optional_skills(
            workspace=workspace,
            optional_skills=optional_skills,
        )
        self._trust_workspace(
            profile=task.assignee,
            workspace=workspace,
            created=created,
        )
