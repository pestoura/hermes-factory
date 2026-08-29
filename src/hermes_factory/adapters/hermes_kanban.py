from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from hermes_factory.contracts.inference_identity import (
    CANONICAL_FACTORY_INFERENCE_IDENTITY,
)
from hermes_factory.skills.system import SkillAdmissionError, SkillRegistry


class NativeKanban(Protocol):
    def create_board(self, slug: str, **kwargs: object) -> dict[str, object]: ...

    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...

    def create_task(self, conn: object, **kwargs: object) -> str: ...

    def add_comment(
        self,
        conn: object,
        task_id: str,
        author: str,
        body: str,
    ) -> int: ...

    def unblock_task(self, conn: object, task_id: str) -> bool: ...

    def list_tasks(
        self, conn: object, *, include_archived: bool = False
    ) -> list[object]: ...

    def child_ids(self, conn: object, task_id: str) -> list[str]: ...

    def archive_task(self, conn: object, task_id: str) -> bool: ...


class TaskSkillPreparer(Protocol):
    """Prepare task-scoped Factory Skills before native dispatch release."""

    def prepare(self, *, board: str, task_id: str) -> None: ...


@dataclass(frozen=True)
class KanbanTaskProjection:
    project_key: str
    work_package_id: str
    stage: str
    revision: str
    title: str
    body: str
    assignee: str
    approved_skills: tuple[str, ...]
    board: str
    parent_task_ids: tuple[str, ...] = ()
    priority: int = 0
    workspace_kind: str = "scratch"
    workspace_path: str | None = None
    branch_name: str | None = None
    project_id: str | None = None
    model_override: str = CANONICAL_FACTORY_INFERENCE_IDENTITY.model
    provider_override: str = CANONICAL_FACTORY_INFERENCE_IDENTITY.provider

    @property
    def idempotency_key(self) -> str:
        return (
            f"factory:{self.project_key}:{self.work_package_id}:"
            f"{self.stage}:{self.revision}"
        )

    def validate(self) -> None:
        required = {
            "project_key": self.project_key,
            "work_package_id": self.work_package_id,
            "stage": self.stage,
            "revision": self.revision,
            "title": self.title,
            "assignee": self.assignee,
            "board": self.board,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} is required")
        identity = CANONICAL_FACTORY_INFERENCE_IDENTITY
        if (
            self.model_override != identity.model
            or self.provider_override != identity.provider
        ):
            raise ValueError("Factory task inference identity must remain canonical")


class HermesKanbanAdapter:
    """Thin semantic projection over the native Hermes Kanban API.

    The adapter deliberately does not dispatch workers or write Hermes' SQLite
    schema directly. Hermes remains the sole queue/dispatcher owner.

    Task projection fails closed unless a Factory Skill Registry and the exact
    admitted Skill identities are supplied. ``approved_skills`` on the task
    projection is treated as an untrusted task request; effective Skills are
    always recomputed from the canonical consumer policy before native write.

    Factory tasks are projected into Hermes as ``blocked``. Before structured
    dispatch authorization is mirrored into the native task audit trail, the
    configured task Skill preparer must complete. Only then may the adapter call
    Hermes' native ``unblock_task`` primitive. This ensures task-scoped Skill
    projection cannot be bypassed through a legacy authorization path.
    """

    def __init__(
        self,
        native: NativeKanban,
        *,
        skill_registry: SkillRegistry | None = None,
        admitted_skill_ids: frozenset[str] | None = None,
        task_skill_preparer: TaskSkillPreparer | None = None,
    ) -> None:
        if (skill_registry is None) != (admitted_skill_ids is None):
            raise ValueError(
                "skill_registry and admitted_skill_ids must be supplied together"
            )
        self._native = native
        self._skill_registry = skill_registry
        self._admitted_skill_ids = admitted_skill_ids
        self._task_skill_preparer = task_skill_preparer

    @staticmethod
    def high_assurance_config_patch() -> dict[str, dict[str, object]]:
        """Return the verified native Hermes config required by Factory boards.

        Dispatch authorization is enforced by blocked task creation plus the
        native unblock lifecycle, not by an unverified configuration key.
        """
        return {"kanban": {"auto_decompose": False}}

    @staticmethod
    def assert_high_assurance_config(config: Mapping[str, object]) -> None:
        """Fail closed unless resolved native Hermes config disables decomposition."""
        kanban = config.get("kanban")
        if not isinstance(kanban, Mapping):
            raise TypeError("kanban config is required for high-assurance mode")
        if kanban.get("auto_decompose") is not False:
            raise ValueError(
                "kanban.auto_decompose must be false for Factory high-assurance boards"
            )

    def ensure_board(
        self,
        *,
        slug: str,
        name: str,
        description: str,
        default_workdir: str | None,
        project_id: str | None,
    ) -> dict[str, object]:
        if not slug.strip():
            raise ValueError("slug is required")
        if not name.strip():
            raise ValueError("name is required")
        return self._native.create_board(
            slug,
            name=name,
            description=description,
            default_workdir=default_workdir,
            project_id=project_id,
        )

    def _effective_skills(self, spec: KanbanTaskProjection) -> tuple[str, ...]:
        if self._skill_registry is None or self._admitted_skill_ids is None:
            raise SkillAdmissionError(
                "Skill authorization context is required before Kanban task projection"
            )
        return self._skill_registry.effective_skills(
            spec.assignee,
            task_approved=spec.approved_skills,
            admitted=self._admitted_skill_ids,
        )

    def project_task(self, spec: KanbanTaskProjection) -> str:
        spec.validate()
        effective_skills = self._effective_skills(spec)
        with self._native.connect_closing(board=spec.board) as conn:
            return self._native.create_task(
                conn,
                title=spec.title,
                body=spec.body,
                assignee=spec.assignee,
                workspace_kind=spec.workspace_kind,
                workspace_path=spec.workspace_path,
                branch_name=spec.branch_name,
                priority=spec.priority,
                parents=spec.parent_task_ids,
                idempotency_key=spec.idempotency_key,
                skills=effective_skills,
                initial_status="blocked",
                board=spec.board,
                project_id=spec.project_id,
                model_override=spec.model_override,
                provider_override=spec.provider_override,
            )

    def retire_superseded_project_generations(
        self,
        *,
        board: str,
        project_key: str,
        keep_revision: str,
        actor: str,
        source: str,
    ) -> tuple[str, ...]:
        for name, value in {
            "board": board,
            "project_key": project_key,
            "keep_revision": keep_revision,
            "actor": actor,
            "source": source,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} is required")

        prefix = f"factory:{project_key}:"
        with self._native.connect_closing(board=board) as conn:
            active_tasks = tuple(
                self._native.list_tasks(conn, include_archived=False)
            )
            active_ids = {
                str(getattr(task, "id", None))
                for task in active_tasks
                if getattr(task, "id", None) is not None
            }
            candidates: dict[str, object] = {}
            for task in active_tasks:
                task_id = getattr(task, "id", None)
                key = getattr(task, "idempotency_key", None)
                if not isinstance(task_id, str) or not isinstance(key, str):
                    continue
                if not key.startswith(prefix):
                    continue
                parts = key[len(prefix) :].split(":")
                if len(parts) != 3 or not all(parts):
                    continue
                revision = parts[2]
                if revision != keep_revision:
                    candidates[task_id] = task

            unsafe = sorted(
                task_id
                for task_id, task in candidates.items()
                if getattr(task, "status", None) in {"ready", "running", "scheduled", "review"}
            )
            if unsafe:
                raise RuntimeError(
                    "superseded Factory generation has dispatchable tasks: "
                    + ", ".join(unsafe)
                )

            child_map: dict[str, set[str]] = {}
            for task_id in candidates:
                children = set(self._native.child_ids(conn, task_id))
                external_active = sorted(
                    child for child in children
                    if child in active_ids and child not in candidates
                )
                if external_active:
                    raise RuntimeError(
                        f"superseded Factory task {task_id} has active external children: "
                        + ", ".join(external_active)
                    )
                child_map[task_id] = children & candidates.keys()

            order: list[str] = []
            remaining = {
                task_id: set(children)
                for task_id, children in child_map.items()
            }
            while remaining:
                leaves = sorted(
                    (
                        task_id
                        for task_id, children in remaining.items()
                        if not children
                    ),
                    key=lambda task_id: (
                        -int(getattr(candidates[task_id], "created_at", 0) or 0),
                        task_id,
                    ),
                )
                if not leaves:
                    raise RuntimeError(
                        "superseded Factory generation dependency cycle"
                    )
                order.extend(leaves)
                for task_id in leaves:
                    remaining.pop(task_id)
                retired_now = set(leaves)
                for children in remaining.values():
                    children.difference_update(retired_now)

            body = "[factory:generation-retirement/v1] " + json.dumps(
                {
                    "actor": actor,
                    "keep_revision": keep_revision,
                    "project_key": project_key,
                    "source": source,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for task_id in order:
                self._native.add_comment(conn, task_id, actor, body)
                if not self._native.archive_task(conn, task_id):
                    raise RuntimeError(
                        f"native Hermes task {task_id} could not be archived"
                    )
            return tuple(order)


    def authorize_dispatch(
        self,
        *,
        board: str,
        task_id: str,
        actor: str,
        source: str,
    ) -> None:
        for name, value in {
            "board": board,
            "task_id": task_id,
            "actor": actor,
            "source": source,
        }.items():
            if not value.strip():
                raise ValueError(f"{name} is required")

        if self._task_skill_preparer is None:
            raise RuntimeError(
                "task Skill preparation is required before dispatch authorization"
            )
        self._task_skill_preparer.prepare(board=board, task_id=task_id)

        payload = json.dumps(
            {"actor": actor, "source": source, "task_id": task_id},
            sort_keys=True,
            separators=(",", ":"),
        )
        body = f"[factory:dispatch-authorization/v1] {payload}"
        with self._native.connect_closing(board=board) as conn:
            self._native.add_comment(conn, task_id, actor, body)
            if not self._native.unblock_task(conn, task_id):
                raise RuntimeError(
                    f"native Hermes task {task_id} could not release for dispatch"
                )
