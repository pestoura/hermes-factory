from __future__ import annotations

import json
import re
from contextlib import AbstractContextManager
from importlib import import_module, metadata
from pathlib import Path
from typing import Protocol, cast

from hermes_factory.runtime.completion_handoff import (
    CandidateIdentityObserver,
    CompletionHandoffCoordinator,
)
from hermes_factory.runtime.hermes_install_runtime import CommandRunner
from hermes_factory.runtime.task_skills import NativeTask


class InstalledRuntimeBindingError(RuntimeError):
    pass


_CANDIDATE_PATH = re.compile(
    r"(?:^|/)factory-package-candidate-([0-9a-fA-F]{40})(?:/|$)"
)
_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


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
    def resolve_workspace(self, task: object, *, board: str) -> object: ...


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

    def parent_ids(self, conn: object, task_id: str) -> list[str]:
        return self._kb.parent_ids(conn, task_id)

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
