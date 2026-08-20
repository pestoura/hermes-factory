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
        self.unblock_result = True

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

    def add_comment(
        self,
        conn: object,
        task_id: str,
        author: str,
        body: str,
    ) -> int:
        self.calls.append(("add_comment", (task_id, author, body)))
        return 1

    def unblock_task(self, conn: object, task_id: str) -> bool:
        self.calls.append(("unblock_task", task_id))
        return self.unblock_result

    def approve_dispatch(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("approve_dispatch is not a native Hermes primitive")

    def dispatch_once(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("Factory adapter must not own Hermes dispatch")


class FakeTaskSkillPreparer:
    def __init__(self, native: FakeNativeKanban, *, fail: bool = False) -> None:
        self._native = native
        self._fail = fail

    def prepare(self, *, board: str, task_id: str) -> None:
        self._native.calls.append(("prepare_task_skills", (board, task_id)))
        if self._fail:
            raise RuntimeError("task Skill preparation failed")


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
                "factory-security-review",
            }
        ),
        consumers={
            "factory-software-engineer": {
                "required": ("factory-tdd-implementation",),
                "task_optional": (
                    "factory-debugging-systematically",
                    "factory-cli-engineering",
                ),
            }
        },
        superseded=frozenset(),
    )


def _authorized_adapter(
    native: FakeNativeKanban,
    *,
    admitted: frozenset[str] | None = None,
) -> HermesKanbanAdapter:
    return HermesKanbanAdapter(
        native,
        skill_registry=_skill_registry(),
        admitted_skill_ids=(
            admitted
            if admitted is not None
            else frozenset(
                {
                    "factory-tdd-implementation",
                    "factory-debugging-systematically",
                    "factory-cli-engineering",
                }
            )
        ),
    )


def test_projection_uses_native_blocked_task_with_semantic_idempotency_and_no_dispatch() -> None:
    native = FakeNativeKanban()
    adapter = _authorized_adapter(native)

    first = adapter.project_task(_spec())
    second = adapter.project_task(_spec())

    assert first == second == "t_1"
    creates = [payload for name, payload in native.calls if name == "create_task"]
    assert len(creates) == 2
    kwargs = creates[0]
    assert kwargs["idempotency_key"] == "factory:jarvas-cli:WP-001:IMPLEMENT:r3"
    assert kwargs["assignee"] == "factory-software-engineer"
    assert kwargs["parents"] == ("t_parent",)
    assert kwargs["skills"] == ("factory-cli-engineering", "factory-tdd-implementation")
    assert kwargs["board"] == "jarvas-cli"
    assert kwargs["project_id"] == "jarvas-cli"
    assert kwargs["workspace_kind"] == "worktree"
    assert kwargs["initial_status"] == "blocked"


def test_structured_authorization_records_native_audit_then_unblocks_without_dispatching() -> None:
    native = FakeNativeKanban()
    adapter = _authorized_adapter(native)

    task_id = adapter.project_task(_spec())
    adapter.authorize_dispatch(
        board="jarvas-cli",
        task_id=task_id,
        actor="factory-orchestrator",
        source="factory-continuous-handoff",
    )

    comments = [payload for name, payload in native.calls if name == "add_comment"]
    expected_body = (
        '[factory:dispatch-authorization/v1] {"actor":"factory-orchestrator",'
        '"source":"factory-continuous-handoff","task_id":"t_1"}'
    )
    assert comments == [("t_1", "factory-orchestrator", expected_body)]
    unblocks = [payload for name, payload in native.calls if name == "unblock_task"]
    assert unblocks == ["t_1"]
    assert [name for name, _ in native.calls].index("add_comment") < [
        name for name, _ in native.calls
    ].index("unblock_task")


def test_dispatch_authorization_prepares_task_skills_before_audit_or_unblock() -> None:
    native = FakeNativeKanban()
    preparer = FakeTaskSkillPreparer(native)
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
        task_skill_preparer=preparer,
    )

    task_id = adapter.project_task(_spec())
    adapter.authorize_dispatch(
        board="jarvas-cli",
        task_id=task_id,
        actor="factory-orchestrator",
        source="factory-continuous-handoff",
    )

    names = [name for name, _ in native.calls]
    assert names.index("prepare_task_skills") < names.index("add_comment")
    assert names.index("prepare_task_skills") < names.index("unblock_task")
    assert [payload for name, payload in native.calls if name == "prepare_task_skills"] == [
        ("jarvas-cli", "t_1")
    ]


def test_dispatch_authorization_preparer_failure_leaves_task_blocked_without_audit() -> None:
    native = FakeNativeKanban()
    preparer = FakeTaskSkillPreparer(native, fail=True)
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
        task_skill_preparer=preparer,
    )
    task_id = adapter.project_task(_spec())

    with pytest.raises(RuntimeError, match="task Skill preparation failed"):
        adapter.authorize_dispatch(
            board="jarvas-cli",
            task_id=task_id,
            actor="factory-orchestrator",
            source="factory-continuous-handoff",
        )

    assert not any(name == "add_comment" for name, _ in native.calls)
    assert not any(name == "unblock_task" for name, _ in native.calls)


def test_structured_authorization_fails_closed_when_native_unblock_fails() -> None:
    native = FakeNativeKanban()
    native.unblock_result = False
    adapter = _authorized_adapter(native)
    task_id = adapter.project_task(_spec())

    with pytest.raises(RuntimeError, match="could not release"):
        adapter.authorize_dispatch(
            board="jarvas-cli",
            task_id=task_id,
            actor="factory-orchestrator",
            source="factory-continuous-handoff",
        )

    assert any(name == "add_comment" for name, _ in native.calls)
    assert [payload for name, payload in native.calls if name == "unblock_task"] == ["t_1"]


def test_projection_rejects_incomplete_semantic_identity_before_native_write() -> None:
    native = FakeNativeKanban()
    adapter = _authorized_adapter(native)
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


def test_projection_without_skill_authorization_context_fails_closed_before_native_write() -> None:
    native = FakeNativeKanban()
    adapter = HermesKanbanAdapter(native)

    with pytest.raises(SkillAdmissionError, match="authorization context"):
        adapter.project_task(_spec())

    assert not any(name == "connect_closing" for name, _ in native.calls)
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


def test_high_assurance_patch_matches_verified_native_hermes_config_keys() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    assert adapter.high_assurance_config_patch() == {
        "kanban": {
            "auto_decompose": False,
        }
    }


def test_high_assurance_verification_fails_closed_on_permissive_auto_decompose() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    with pytest.raises(ValueError, match="auto_decompose"):
        adapter.assert_high_assurance_config({"kanban": {"auto_decompose": True}})


def test_high_assurance_verification_accepts_native_config_without_fabricated_dispatch_mode() -> None:
    adapter = HermesKanbanAdapter(FakeNativeKanban())

    adapter.assert_high_assurance_config(
        {
            "kanban": {
                "auto_decompose": False,
                "max_spawn": 4,
            },
            "agent": {"max_turns": 500},
        }
    )


def test_task_skill_authorization_is_recomputed_and_aliases_are_canonicalized() -> None:
    native = FakeNativeKanban()
    adapter = _authorized_adapter(
        native,
        admitted=frozenset(
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
    adapter = _authorized_adapter(
        native,
        admitted=frozenset(
            {
                "factory-tdd-implementation",
                "factory-debugging-systematically",
                "factory-cli-engineering",
                "factory-security-review",
            }
        ),
    )
    spec = _spec()

    with pytest.raises(SkillAdmissionError, match="not authorized"):
        adapter.project_task(
            KanbanTaskProjection(
                **{
                    **spec.__dict__,
                    "approved_skills": ("factory-security-review",),
                }
            )
        )

    assert not any(name == "connect_closing" for name, _ in native.calls)
    assert not any(name == "create_task" for name, _ in native.calls)


def test_task_skill_authorization_rejects_unadmitted_required_skill_before_write() -> None:
    native = FakeNativeKanban()
    adapter = _authorized_adapter(
        native,
        admitted=frozenset({"factory-debugging-systematically"}),
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

    assert not any(name == "connect_closing" for name, _ in native.calls)
    assert not any(name == "create_task" for name, _ in native.calls)
