from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from hermes_factory.adapters.hermes_kanban import HermesKanbanAdapter


class FakeNativeKanban:
    def __init__(self, tasks, children=None):
        self.tasks = {task.id: task for task in tasks}
        self.children = children or {}
        self.calls = []
        self.archive_fail_for = set()

    @property
    def archived(self):
        return [call[1] for call in self.calls if call[0] == "archive" and self.tasks[call[1]].status == "archived"]

    @property
    def comments(self):
        return [(call[1], call[2], call[3]) for call in self.calls if call[0] == "comment"]

    @contextmanager
    def connect_closing(self, *, board: str):
        self.calls.append(("connect", board))
        yield object()

    def list_tasks(self, conn, *, include_archived=False):
        return [
            task for task in self.tasks.values()
            if include_archived or task.status != "archived"
        ]

    def child_ids(self, conn, task_id: str):
        return list(self.children.get(task_id, ()))

    def add_comment(self, conn, task_id: str, author: str, body: str):
        self.calls.append(("comment", task_id, author, body))
        return 1

    def archive_task(self, conn, task_id: str):
        self.calls.append(("archive", task_id))
        task = self.tasks[task_id]
        if task_id in self.archive_fail_for or task.status == "archived":
            return False
        task.status = "archived"
        return True


def _task(task_id: str, *, revision: str | None, status="blocked", created_at=1):
    key = None
    if revision is not None:
        key = f"factory:jarvas-cli:WP-A:DISCOVER:{revision}"
    return SimpleNamespace(
        id=task_id,
        idempotency_key=key,
        status=status,
        created_at=created_at,
    )

def test_retirement_archives_only_superseded_factory_generations_descendants_first():
    old = "a" * 64 + ".stage-contract-v9"
    current = "a" * 64 + ".stage-contract-v10"
    parent = _task("t_parent", revision=old, created_at=1)
    child = _task("t_child", revision=old, created_at=2)
    keep = _task("t_keep", revision=current, created_at=3)
    manual = _task("t_manual", revision=None, created_at=4)
    native = FakeNativeKanban(
        [parent, child, keep, manual],
        {"t_parent": ("t_child",)},
    )

    retired = HermesKanbanAdapter(native).retire_superseded_project_generations(
        board="jarvas-cli",
        project_key="jarvas-cli",
        keep_revision=current,
        actor="factory-orchestrator",
        source="factory-project-materialization",
    )

    assert retired == ("t_child", "t_parent")
    assert keep.status == "blocked"
    assert manual.status == "blocked"
    archives = [call[1] for call in native.calls if call[0] == "archive"]
    assert archives == ["t_child", "t_parent"]
    comments = [call for call in native.calls if call[0] == "comment"]
    assert len(comments) == 2
    assert all("[factory:generation-retirement/v1]" in call[3] for call in comments)
    assert all(current in call[3] for call in comments)


def test_retirement_fails_closed_before_writes_when_superseded_task_is_dispatchable():
    old = "a" * 64 + ".stage-contract-v9"
    for status in ("ready", "running", "scheduled", "review"):
        task = _task("t_old", revision=old, created_at=1)
        task.status = status
        native = FakeNativeKanban([task])
        with pytest.raises(RuntimeError, match="dispatchable tasks"):
            HermesKanbanAdapter(native).retire_superseded_project_generations(
                board="jarvas-cli", project_key="jarvas-cli",
                keep_revision="a" * 64 + ".stage-contract-v10",
                actor="factory-orchestrator", source="factory-project-materialization",
            )
        assert native.archived == []
        assert native.comments == []


def test_retirement_fails_closed_on_active_external_child():
    old = _task("t_old", revision="a" * 64 + ".stage-contract-v9", created_at=1)
    external = _task("t_external", revision=None, created_at=2)
    native = FakeNativeKanban([old, external], {"t_old": ("t_external",)})
    with pytest.raises(RuntimeError, match="active external children"):
        HermesKanbanAdapter(native).retire_superseded_project_generations(
            board="jarvas-cli", project_key="jarvas-cli",
            keep_revision="a" * 64 + ".stage-contract-v10",
            actor="factory-orchestrator", source="factory-project-materialization",
        )
    assert native.archived == []


def test_retirement_is_idempotent_when_only_current_generation_remains():
    current = "a" * 64 + ".stage-contract-v10"
    keep = _task("t_keep", revision=current, created_at=1)
    manual = _task("t_manual", revision=None, created_at=2)
    native = FakeNativeKanban([keep, manual])
    retired = HermesKanbanAdapter(native).retire_superseded_project_generations(
        board="jarvas-cli", project_key="jarvas-cli", keep_revision=current,
        actor="factory-orchestrator", source="factory-project-materialization",
    )
    assert retired == ()
    assert native.archived == []
    assert native.comments == []


def test_retirement_stops_on_native_archive_failure_without_authorizing_anything():
    old = "a" * 64 + ".stage-contract-v9"
    child = _task("t_child", revision=old, created_at=2)
    parent = _task("t_parent", revision=old, created_at=1)
    native = FakeNativeKanban([parent, child], {"t_parent": ("t_child",)})
    native.archive_fail_for = {"t_parent"}
    with pytest.raises(RuntimeError, match="could not be archived"):
        HermesKanbanAdapter(native).retire_superseded_project_generations(
            board="jarvas-cli", project_key="jarvas-cli",
            keep_revision="a" * 64 + ".stage-contract-v10",
            actor="factory-orchestrator", source="factory-project-materialization",
        )
    assert native.archived == ["t_child"]
    assert [task_id for task_id, _, _ in native.comments] == ["t_child", "t_parent"]
