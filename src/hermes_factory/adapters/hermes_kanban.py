from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from hermes_factory.skills.system import SkillAdmissionError, SkillRegistry


class NativeKanban(Protocol):
    def create_board(self, slug: str, **kwargs: object) -> dict[str, object]: ...

    def connect_closing(self, *, board: str) -> AbstractContextManager[object]: ...

    def create_task(self, conn: object, **kwargs: object) -> str: ...

    def approve_dispatch(
        self,
        conn: object,
        task_id: str,
        *,
        actor: str,
        source: str,
    ) -> object: ...


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
    project_id: str | None = None

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


class HermesKanbanAdapter:
    """Thin semantic projection over the native Hermes Kanban API.

    The adapter deliberately does not dispatch workers or write Hermes' SQLite
    schema directly. Hermes remains the sole queue/dispatcher owner.

    Task projection fails closed unless a Factory Skill Registry and the exact
    admitted Skill identities are supplied. ``approved_skills`` on the task
    projection is treated as an untrusted task request; effective Skills are
    always recomputed from the canonical consumer policy before native write.
    """

    def __init__(
        self,
        native: NativeKanban,
        *,
        skill_registry: SkillRegistry | None = None,
        admitted_skill_ids: frozenset[str] | None = None,
    ) -> None:
        if (skill_registry is None) != (admitted_skill_ids is None):
            raise ValueError(
                "skill_registry and admitted_skill_ids must be supplied together"
            )
        self._native = native
        self._skill_registry = skill_registry
        self._admitted_skill_ids = admitted_skill_ids

    @staticmethod
    def high_assurance_config_patch() -> dict[str, dict[str, object]]:
        """Return the minimal native Hermes config required by Factory boards.

        This is a projection, not a live mutation. Phase P applies the patch
        through Hermes' supported configuration surface and then calls
        :meth:`assert_high_assurance_config` against the resolved config.
        """
        return {
            "kanban": {
                "auto_decompose": False,
                "dispatch_approval_mode": "structured",
            }
        }

    @staticmethod
    def assert_high_assurance_config(config: Mapping[str, object]) -> None:
        """Fail closed unless the resolved Hermes config enforces Factory policy."""
        kanban = config.get("kanban")
        if not isinstance(kanban, Mapping):
            raise TypeError("kanban config is required for high-assurance mode")
        if kanban.get("auto_decompose") is not False:
            raise ValueError(
                "kanban.auto_decompose must be false for Factory high-assurance boards"
            )
        if kanban.get("dispatch_approval_mode") != "structured":
            raise ValueError(
                "kanban.dispatch_approval_mode must be structured for Factory high-assurance boards"
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
                priority=spec.priority,
                parents=spec.parent_task_ids,
                idempotency_key=spec.idempotency_key,
                skills=effective_skills,
                board=spec.board,
                project_id=spec.project_id,
            )

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
        with self._native.connect_closing(board=board) as conn:
            self._native.approve_dispatch(
                conn,
                task_id,
                actor=actor,
                source=source,
            )
