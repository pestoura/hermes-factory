from contextlib import contextmanager

import pytest

from hermes_factory.adapters.hermes_kanban import (
    HermesKanbanAdapter,
    KanbanTaskProjection,
)
from hermes_factory.skills.system import SkillAdmissionError, SkillRegistry


class FakeNativeKanban:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.ids_by_key: dict[str, str] = {}
        self.counter = 0

    def create_board(self, slug: str, **kwargs: object) -> dict[str, object]:
        self.calls.append(("create_board", (slug, kwargs)))
        return {"slug": slug, **kwargs}

    @contextmanager
    def connect_closing(self, *, board: str):
        self.calls.append(("connect_closing", board))
        yield object()

    def create_task(self, conn: object, **kwargs: object) -> str:
        self.calls.append(("create_task", kwargs))
        key = str(kwargs["idempotency_key"])
        if key not in self.ids_by_key:
            self.counter += 1
            self.ids_by_key[key] = f"t_{self.counter}"
        return self.ids_by_key[key]

    def approve_dispatch(
        self,
        conn: object,
        task_id: str,
        *,
        actor: str,
        source: str,
        **kwargs: object,
    ) -> object:
        self.calls.append(("approve_dispatch", (task_id, actor, source, kwargs)))
        return None

    def dispatch_once(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("Factory adapter must not own Hermes dispatch")


def _spec() -> KanbanTaskProjection:
    return KanbanTaskProjection(
        project_key="jarvas-cli",
        work_package_id="WP-001",
        stage="IMPLEMENT",
        revision="r3",
        title="Implement status command",
        body="Implement the approved WP contract.",
        assignee="factory-software-engineer",
        approved_skills=("factory-tdd-implementation", "factory-cli-engineering"),
        board="jarvas-cli",
        parent_task_ids=("t_parent",),
        priority=20,
        workspace_kind="worktree",
        project_id="jarvas-cli",
    )


def _skill_registry() -> SkillRegistry:
    return SkillRegistry(
        aliases={"legacy-debug": "factory-debugging-systematically"},
        registered=frozenset(
            {
                "factory-tdd-implementation",
                "factory-debugging-systematically",
                "factory-cli-engineering",
            }
        ),
        consumers={
            "factory-software-engineer": {
                "required": ("factory-tdd-implementation",),
                "task_optional": ("factory-debugging-systematically",),
            }
        },
        superseded=frozenset(),
    )


def test_projection_uses_native_task_with_semantic_idempotency_and_no_dispatch() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(native)

    first = adapter.project_task(_spec())
    second = adapter.project_task(_spec())

    assert first == second == "t_1"
    creates = [payload for name, payload in native.calls if name == "create_task"]
    assert len(creates) == 2
    kwargs = creates[0]
    assert kwargs["idempotency_key"] == "factory:jarvas-cli:WP-001:IMPLEMENT:r3"
    assert kwargs["assignee"] == "factory-software-engineer"
    assert kwargs["parents"] == ("t_parent",)
    assert kwargs["skills"] == ("factory-tdd-implementation", "factory-cli-engineering")
    assert kwargs["board"] == "jarvas-cli"
    assert kwargs["project_id"] == "jarvas-cli"
    assert kwargs["workspace_kind"] == "worktree"


def test_structured_authorization_uses_native_approval_and_never_dispatches() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(native)

    task_id = adapter.project_task(_spec())
    adapter.authorize_dispatch(
        board="jarvas-cli",
        task_id=task_id,
        actor="factory-orchestrator",
        source="factory-continuous-handoff",
    )

    approvals = [payload for name, payload in native.calls if name == "approve_dispatch"]
    assert approvals == [
        (
            "t_1",
            "factory-orchestrator",
            "factory-continuous-handoff",
            {},
        )
    ]


def test_projection_rejects_incomplete_semantic_identity_before_native_write() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(native)
    spec = _spec()

    with pytest.raises(ValueError, match="work_package_id"):
        adapter.project_task(
            KanbanTaskProjection(
                **{
                    **spec.__dict__,
                    "work_package_id": "",
                }
            )
        )

    assert not any(name == "create_task" for name, _ in native.calls)


def test_board_reconciliation_uses_native_idempotent_board_api() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(native)

    first = adapter.ensure_board(
        slug="jarvas-cli",
        name="Jarvas CLI",
        description="First Factory greenfield project",
        default_workdir="/srv/jarvas-cli",
        project_id="jarvas-cli",
    )
    second = adapter.ensure_board(
        slug="jarvas-cli",
        name="Jarvas CLI",
        description="First Factory greenfield project",
        default_workdir="/srv/jarvas-cli",
        project_id="jarvas-cli",
    )

    assert first["slug"] == second["slug"] == "jarvas-cli"
    creates = [payload for name, payload in native.calls if name == "create_board"]
    assert creates == [
        (
            "jarvas-cli",
            {
                "name": "Jarvas CLI",
                "description": "First Factory greenfield project",
                "default_workdir": "/srv/jarvas-cli",
                "project_id": "jarvas-cli",
            },
        ),
        (
            "jarvas-cli",
            {
                "name": "Jarvas CLI",
                "description": "First Factory greenfield project",
                "default_workdir": "/srv/jarvas-cli",
                "project_id": "jarvas-cli",
            },
        ),
    ]


def test_high_assurance_patch_matches_native_hermes_config_keys() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    assert adapter.high_assurance_config_patch() == {
        "kanban": {
            "auto_decompose": False,
            "dispatch_approval_mode": "structured",
        }
    }


def test_high_assurance_verification_fails_closed_on_permissive_defaults() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    with pytest.raises(ValueError, match="auto_decompose"):
        adapter.assert_high_assurance_config(
            {
                "kanban": {
                    "auto_decompose": True,
                    "dispatch_approval_mode": "compat",
                }
            }
        )


def test_high_assurance_verification_accepts_required_values_with_extra_config() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    adapter.assert_high_assurance_config(
        {
            "kanban": {
                "auto_decompose": False,
                "dispatch_approval_mode": "structured",
                "max_spawn": 4,
            },
            "agent": {"max_turns": 500},
        }
    )


def test_high_assurance_verification_rejects_missing_or_compat_dispatch_mode() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    with pytest.raises(ValueError, match="dispatch_approval_mode"):
        adapter.assert_high_assurance_config(
            {"kanban": {"auto_decompose": False}}
        )
    with pytest.raises(ValueError, match="dispatch_approval_mode"):
        adapter.assert_high_assurance_config(
            {
                "kanban": {
                    "auto_decompose": False,
                    "dispatch_approval_mode": "compat",
                }
            }
        )


def test_task_skill_authorization_is_recomputed_and_aliases_are_canonicalized() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(
        native,
        skill_registry=_skill_registry(),
        admitted_skill_ids=frozenset(
            {"factory-tdd-implementation", "factory-debugging-systematically"}
        ),
    )
    spec = _spec()

    task_id = adapter.project_task(
        KanbanTaskProjection(
            **{
                **spec.__dict__,
                "approved_skills": ("legacy-debug",),
            }
        )
    )

    assert task_id == "t_1"
    creates = [payload for name, payload in native.calls if name == "create_task"]
    assert creates[0]["skills"] == (
        "factory-debugging-systematically",
        "factory-tdd-implementation",
    )


def test_task_skill_authorization_rejects_registered_but_unauthorized_skill_before_write() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(
        native,
        skill_registry=_skill_registry(),
        admitted_skill_ids=frozenset(
            {
                "factory-tdd-implementation",
                "factory-debugging-systematically",
                "factory-cli-engineering",
            }
        ),
    )
    spec = _spec()

    with pytest.raises(SkillAdmissionError, match="not authorized"):
        adapter.project_task(
            KanbanTaskProjection(
                **{
                    **spec.__dict__,
                    "approved_skills": ("factory-cli-engineering",),
                }
            )
        )

    assert not any(name == "create_task" for name, _ in native.calls)


def test_task_skill_authorization_rejects_unadmitted_required_skill_before_write() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(
        native,
        skill_registry=_skill_registry(),
        admitted_skill_ids=frozenset({"factory-debugging-systematically"}),
    )
    spec = _spec()

    with pytest.raises(SkillAdmissionError, match="not admitted"):
        adapter.project_task(
            KanbanTaskProjection(
                **{
                    **spec.__dict__,
                    "approved_skills": ("factory-debugging-systematically",),
                }
            )
        )

    assert not any(name == "create_task" for name, _ in native.calls)
