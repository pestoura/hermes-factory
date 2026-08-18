from contextlib import contextmanager

import pytest

from hermes_factory.adapters.hermes_kanban import (
    HermesKanbanAdapter,
    KanbanTaskProjection,
)


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
