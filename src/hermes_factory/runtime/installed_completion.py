from __future__ import annotations

import json
import re
from contextlib import AbstractContextManager
from importlib import import_module, metadata
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

from hermes_factory.runtime.completion_handoff import (
    CandidateIdentityObserver,
    CompletionHandoffCoordinator,
)
from hermes_factory.runtime.hermes_install_runtime import CommandRunner
from hermes_factory.runtime.project_materializer import stage_mutation_policy
from hermes_factory.runtime.task_skills import NativeTask
from hermes_factory.runtime.upstream_rework import (
    UpstreamReworkCoordinator,
    is_upstream_rework_task_key,
)


class InstalledRuntimeBindingError(RuntimeError):
    pass


_CANDIDATE_PATH = re.compile(
    r"(?:^|/)factory-package-candidate-([0-9a-fA-F]{40})(?:/|$)"
)
_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_FACTORY_STAGE_KEY = re.compile(
    r"^factory:[^:]+:[^:]+:(?P<stage>[A-Z0-9_]+):[0-9a-f]{64}"
    r"(?:\.stage-contract-v[1-9][0-9]*)?$"
)


def resolve_shared_hermes_home(*, hermes_home: str | None = None) -> Path:
    """Resolve the Hermes root that owns shared Factory catalog and ledger state.

    Worker Profiles run with HERMES_HOME=<root>/profiles/<profile>, but the
    Factory skill catalog and semantic registry are shared runtime authorities
    staged under the parent Hermes root. An explicit hermes_home argument is
    treated as an operator-supplied shared root; HERMES_FACTORY_HOME provides
    the same explicit override for runtime processes.
    """
    import os
    explicit = hermes_home or os.environ.get("HERMES_FACTORY_HOME")
    if explicit:
        return Path(explicit).expanduser()

    active = os.environ.get("HERMES_HOME")
    if active:
        active_home = Path(active).expanduser()
        if active_home.parent.name == "profiles":
            return active_home.parent.parent
        return active_home
    return Path.home() / ".hermes"


class DistributionLike(Protocol):
    def read_text(self, filename: str) -> str | None: ...


class NativeKanbanModule(Protocol):
    def create_board(self, slug: str, **kwargs: object) -> dict[str, object]: ...
    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...
    def create_task(self, conn: object, **kwargs: object) -> str: ...
    def add_comment(self, conn: object, task_id: str, author: str, body: str) -> int: ...
    def unblock_task(self, conn: object, task_id: str) -> bool: ...
    def get_task(self, conn: object, task_id: str) -> object | None: ...
    def latest_run(self, conn: object, task_id: str) -> object | None: ...
    def child_ids(self, conn: object, task_id: str) -> list[str]: ...
    def parent_ids(self, conn: object, task_id: str) -> list[str]: ...
    def link_tasks(self, conn: object, parent_id: str, child_id: str) -> None: ...
    def resolve_workspace(self, task: object, *, board: str) -> object: ...
    def list_tasks(self, conn: object, *, include_archived: bool = False) -> list[object]: ...
    def archive_task(self, conn: object, task_id: str) -> bool: ...


def active_factory_candidate_sha(
    *, distribution: DistributionLike | None = None
) -> str:
    dist = distribution or metadata.distribution("hermes-factory")
    raw = dist.read_text("direct_url.json")
    if not raw:
        raise InstalledRuntimeBindingError(
            "installed hermes-factory direct_url.json is unavailable"
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstalledRuntimeBindingError(
            "installed hermes-factory direct_url.json is invalid"
        ) from exc
    url = payload.get("url") if isinstance(payload, dict) else None
    if not isinstance(url, str):
        raise InstalledRuntimeBindingError(
            "installed hermes-factory candidate SHA is unavailable"
        )
    match = _CANDIDATE_PATH.search(url)
    if match is None:
        raise InstalledRuntimeBindingError(
            "installed hermes-factory candidate SHA is unavailable"
        )
    return match.group(1).lower()


_DOC_SUFFIXES = frozenset({".md", ".rst", ".adoc", ".txt", ".puml", ".plantuml", ".mmd", ".drawio"})
_DOC_ROOTS = frozenset({"docs", "doc", "documentation"})
_TEST_PARTS = frozenset({"test", "tests", "__tests__", "spec"})


class StageMutationObserver(Protocol):
    def observe(
        self, *, task: object, base_candidate_identity: str | None
    ) -> tuple[str, ...]: ...


def _repository_path_kind(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    pure = PurePosixPath(normalized)
    parts = tuple(part.lower() for part in pure.parts)
    if not parts:
        return "production"
    if parts[0] in _DOC_ROOTS or pure.suffix.lower() in _DOC_SUFFIXES:
        return "docs"
    name = pure.name.lower()
    stem = pure.stem.lower()
    if (
        any(part in _TEST_PARTS for part in parts[:-1])
        or stem.startswith("test_")
        or stem.endswith("_test")
        or ".test." in name
        or ".spec." in name
    ):
        return "test"
    return "production"


def validate_factory_stage_mutation_paths(
    *, stage: str, changed_paths: tuple[str, ...]
) -> None:
    policy = stage_mutation_policy(stage)
    kinds = {path: _repository_path_kind(path) for path in changed_paths}
    if policy in {"engineering_docs_only", "evidence_docs_only"}:
        violations = tuple(path for path, kind in kinds.items() if kind != "docs")
        if violations:
            raise InstalledRuntimeBindingError(
                f"{stage} repository mutation policy prohibits production/test changes: "
                + ", ".join(violations[:10])
            )
        return
    if policy == "tests_and_docs_only":
        violations = tuple(path for path, kind in kinds.items() if kind == "production")
        if violations:
            raise InstalledRuntimeBindingError(
                f"{stage} repository mutation policy prohibits production source changes: "
                + ", ".join(violations[:10])
            )
        return
    if policy == "implementation_no_tests":
        violations = tuple(path for path, kind in kinds.items() if kind == "test")
        if violations:
            raise InstalledRuntimeBindingError(
                f"{stage} repository mutation policy prohibits test changes: "
                + ", ".join(violations[:10])
            )
        return
    raise InstalledRuntimeBindingError(f"unsupported repository mutation policy for {stage}")


class GitStageMutationObserver:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    def observe(
        self, *, task: object, base_candidate_identity: str | None
    ) -> tuple[str, ...]:
        path = getattr(task, "workspace_path", None)
        if not isinstance(path, str) or not path.strip():
            raise InstalledRuntimeBindingError("stage mutation worktree path is unavailable")
        workspace = path.strip()
        argv: tuple[str, ...]
        if base_candidate_identity is not None:
            base = base_candidate_identity.strip().lower()
            if not _GIT_SHA.fullmatch(base):
                raise InstalledRuntimeBindingError("parent candidate identity is not an exact Git SHA")
            argv = (
                "git", "-C", workspace, "diff", "--name-only",
                "--diff-filter=ACMRD", f"{base}..HEAD", "--",
            )
        else:
            argv = (
                "git", "-C", workspace, "diff-tree", "--no-commit-id",
                "--name-only", "-r", "HEAD", "--",
            )
        result = self._runner.run(argv)
        if result.returncode != 0:
            raise InstalledRuntimeBindingError("stage repository delta is unavailable")
        return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _factory_stage_from_task(task: object) -> str | None:
    key = getattr(task, "idempotency_key", None)
    if not isinstance(key, str):
        return None
    match = _FACTORY_STAGE_KEY.fullmatch(key.strip())
    return match.group("stage") if match is not None else None


def _parent_candidate_identity(*, board: str, task: object) -> str | None:
    task_id = getattr(task, "id", None)
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    kb = cast(NativeKanbanModule, import_module("hermes_cli.kanban_db"))
    with kb.connect_closing(board=board) as conn:
        parents = tuple(kb.parent_ids(conn, task_id.strip()))
        if len(parents) == 1:
            baseline_parent = parents[0]
        else:
            rework_parents = tuple(
                parent_id
                for parent_id in parents
                if (
                    (parent := kb.get_task(conn, parent_id)) is not None
                    and is_upstream_rework_task_key(
                        getattr(parent, "idempotency_key", None)
                    )
                )
            )
            if len(rework_parents) != 1:
                return None
            baseline_parent = rework_parents[0]
        run = kb.latest_run(conn, baseline_parent)
    if run is None:
        return None
    raw = getattr(run, "metadata", None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None
    handoff = raw.get("factory_handoff")
    if not isinstance(handoff, dict):
        return None
    candidate = handoff.get("candidate_identity")
    if not isinstance(candidate, str) or not _GIT_SHA.fullmatch(candidate.strip()):
        return None
    return candidate.strip().lower()


class GitCandidateIdentityObserver:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    def observe(self, *, board: str, task: object) -> str | None:
        del board
        path = getattr(task, "workspace_path", None)
        if not isinstance(path, str) or not path.strip():
            raise InstalledRuntimeBindingError(
                "candidate worktree path is unavailable"
            )
        workspace = path.strip()
        status = self._runner.run(("git", "-C", workspace, "status", "--porcelain"))
        if status.returncode != 0:
            raise InstalledRuntimeBindingError("candidate worktree status is unavailable")
        if status.stdout.strip():
            raise InstalledRuntimeBindingError("candidate worktree is dirty")
        head = self._runner.run(("git", "-C", workspace, "rev-parse", "HEAD"))
        if head.returncode != 0:
            raise InstalledRuntimeBindingError("candidate HEAD is unavailable")
        sha = head.stdout.strip()
        if not _GIT_SHA.fullmatch(sha):
            raise InstalledRuntimeBindingError("candidate HEAD is not an exact Git SHA")
        return sha.lower()


def validate_factory_repository_precompletion(
    *,
    board: str,
    task: object,
    candidate_identity: str | None,
    observer: CandidateIdentityObserver | None = None,
    stage: str | None = None,
    base_candidate_identity: str | None = None,
    mutation_observer: StageMutationObserver | None = None,
) -> str:
    """Fail closed on dirty/stale repository state before durable completion."""
    if observer is None:
        from hermes_factory.runtime.hermes_install_runtime import SubprocessCommandRunner

        observer = GitCandidateIdentityObserver(SubprocessCommandRunner())
    observed = observer.observe(board=board, task=task)
    if not isinstance(observed, str) or not _GIT_SHA.fullmatch(observed.strip()):
        raise InstalledRuntimeBindingError(
            "candidate HEAD observation is not an exact Git SHA"
        )
    observed_sha = observed.strip().lower()
    if candidate_identity is not None:
        expected = candidate_identity.strip().lower()
        if expected != observed_sha:
            raise InstalledRuntimeBindingError(
                "candidate identity does not match clean worktree HEAD"
            )
    resolved_stage = stage or _factory_stage_from_task(task)
    resolved_base = base_candidate_identity
    if stage is None and resolved_stage is not None and resolved_base is None:
        resolved_base = _parent_candidate_identity(board=board, task=task)
    if resolved_stage is not None:
        if mutation_observer is None:
            from hermes_factory.runtime.hermes_install_runtime import SubprocessCommandRunner

            mutation_observer = GitStageMutationObserver(SubprocessCommandRunner())
        changed_paths = mutation_observer.observe(
            task=task, base_candidate_identity=resolved_base
        )
        validate_factory_stage_mutation_paths(
            stage=resolved_stage, changed_paths=changed_paths
        )
    return observed_sha


class HermesNativeKanbanRuntime:
    """Adapter over Hermes' native kanban_db module."""

    def __init__(self, kb: NativeKanbanModule) -> None:
        self._kb = kb

    def create_board(self, slug: str, **kwargs: object) -> dict[str, object]:
        return self._kb.create_board(slug, **kwargs)

    def connect_closing(self, *, board: str) -> AbstractContextManager[object]:
        return self._kb.connect_closing(board=board)

    def create_task(self, conn: object, **kwargs: object) -> str:
        return self._kb.create_task(conn, **kwargs)

    def add_comment(self, conn: object, task_id: str, author: str, body: str) -> int:
        return self._kb.add_comment(conn, task_id, author, body)

    def unblock_task(self, conn: object, task_id: str) -> bool:
        return self._kb.unblock_task(conn, task_id)

    def get_task(self, conn: object, task_id: str) -> NativeTask | None:
        return cast(NativeTask | None, self._kb.get_task(conn, task_id))

    def latest_run(self, conn: object, task_id: str) -> object | None:
        return self._kb.latest_run(conn, task_id)

    def child_ids(self, conn: object, task_id: str) -> list[str]:
        return self._kb.child_ids(conn, task_id)

    def list_tasks(self, conn: object, *, include_archived: bool = False) -> list[object]:
        return list(self._kb.list_tasks(conn, include_archived=include_archived))

    def archive_task(self, conn: object, task_id: str) -> bool:
        return self._kb.archive_task(conn, task_id)

    def parent_ids(self, conn: object, task_id: str) -> list[str]:
        return self._kb.parent_ids(conn, task_id)

    def link_tasks(self, conn: object, parent_id: str, child_id: str) -> None:
        self._kb.link_tasks(conn, parent_id, child_id)

    def resolve_workspace(self, task: NativeTask, *, board: str) -> str:
        return str(self._kb.resolve_workspace(task, board=board))


def build_installed_completion_coordinator(
    *,
    hermes_home: str | None = None,
    registry_path: str | None = None,
) -> CompletionHandoffCoordinator:
    import os
    from pathlib import Path

    kb = cast(NativeKanbanModule, import_module("hermes_cli.kanban_db"))

    from hermes_factory.adapters.hermes_kanban import HermesKanbanAdapter
    from hermes_factory.handoff.ledger import SemanticHandoffLedger
    from hermes_factory.handoff.service import HandoffService
    from hermes_factory.runtime.hermes_install_runtime import SubprocessCommandRunner
    from hermes_factory.runtime.skill_catalog_candidate import load_skill_catalog_candidate
    from hermes_factory.runtime.task_skills import HermesTaskSkillPreparer
    from hermes_factory.skills.system import SkillRegistry
    from hermes_factory.traceability.registry import SemanticRegistry

    home = resolve_shared_hermes_home(hermes_home=hermes_home)
    candidate_sha = active_factory_candidate_sha()
    candidate = load_skill_catalog_candidate(
        candidate_root=home / "factory" / "skill-catalog" / candidate_sha,
        expected_candidate_sha=candidate_sha,
    )
    skill_registry = SkillRegistry.from_document(candidate.registry_document)
    admitted = frozenset(candidate.skill_digests)
    native = HermesNativeKanbanRuntime(kb)
    runner = SubprocessCommandRunner()
    preparer = HermesTaskSkillPreparer(
        native=native,
        skill_registry=skill_registry,
        admitted_skill_ids=admitted,
        skill_sources=candidate.skill_sources,
        expected_skill_digests=candidate.skill_digests,
        command_runner=runner,
    )
    kanban = HermesKanbanAdapter(
        native,
        skill_registry=skill_registry,
        admitted_skill_ids=admitted,
        task_skill_preparer=preparer,
    )
    semantic_path = Path(
        registry_path
        or os.environ.get("HERMES_FACTORY_REGISTRY_PATH")
        or (home / "factory" / "state.sqlite3")
    ).expanduser()
    handoff = HandoffService(
        ledger=SemanticHandoffLedger(SemanticRegistry(semantic_path)),
        kanban=kanban,
    )
    return CompletionHandoffCoordinator(
        native=native,
        handoff_service=handoff,
        candidate_observer=GitCandidateIdentityObserver(runner),
    )


def build_installed_upstream_rework_coordinator(
    *,
    hermes_home: str | None = None,
) -> UpstreamReworkCoordinator:
    from hermes_factory.adapters.hermes_kanban import HermesKanbanAdapter
    from hermes_factory.runtime.hermes_install_runtime import SubprocessCommandRunner
    from hermes_factory.runtime.skill_catalog_candidate import load_skill_catalog_candidate
    from hermes_factory.runtime.task_skills import HermesTaskSkillPreparer
    from hermes_factory.skills.system import SkillRegistry

    kb = cast(NativeKanbanModule, import_module("hermes_cli.kanban_db"))
    native = HermesNativeKanbanRuntime(kb)
    home = resolve_shared_hermes_home(hermes_home=hermes_home)
    candidate_sha = active_factory_candidate_sha()
    candidate = load_skill_catalog_candidate(
        candidate_root=home / "factory" / "skill-catalog" / candidate_sha,
        expected_candidate_sha=candidate_sha,
    )
    skill_registry = SkillRegistry.from_document(candidate.registry_document)
    admitted = frozenset(candidate.skill_digests)
    runner = SubprocessCommandRunner()
    preparer = HermesTaskSkillPreparer(
        native=native,
        skill_registry=skill_registry,
        admitted_skill_ids=admitted,
        skill_sources=candidate.skill_sources,
        expected_skill_digests=candidate.skill_digests,
        command_runner=runner,
    )
    adapter = HermesKanbanAdapter(
        native,
        skill_registry=skill_registry,
        admitted_skill_ids=admitted,
        task_skill_preparer=preparer,
    )
    return UpstreamReworkCoordinator(
        native=native,
        adapter=adapter,
        candidate_observer=GitCandidateIdentityObserver(runner),
    )
