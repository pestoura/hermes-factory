import importlib.util
from pathlib import Path
from types import SimpleNamespace

PLUGIN = Path("hermes-integration/dashboard-plugin/hermes-factory/__init__.py")


def _load_plugin():
    spec = importlib.util.spec_from_file_location("factory_plugin_test", PLUGIN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCoordinator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def on_task_completed(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("handoff proof missing")
        return ()


def test_non_factory_completion_is_ignored_before_runtime_builder(monkeypatch) -> None:
    plugin = _load_plugin()
    built = []
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(idempotency_key=None),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator",
        lambda: built.append(True),
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="misc")

    assert built == []


def test_factory_completion_invokes_installed_coordinator(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeCoordinator()
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key="factory:jarvas-cli:WP-A:SPECIFY:" + "a" * 64
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator", lambda: coordinator,
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="jarvas-cli")

    assert coordinator.calls == [{"task_id": "t_1", "board": "jarvas-cli"}]


def test_factory_handoff_failure_records_blocked_diagnostic_without_raising(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeCoordinator(fail=True)
    recorded = []
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key="factory:jarvas-cli:WP-A:SPECIFY:" + "a" * 64
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator", lambda: coordinator,
    )
    monkeypatch.setattr(
        plugin, "_record_handoff_blocked", lambda **kwargs: recorded.append(kwargs),
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="jarvas-cli")

    assert coordinator.calls == [{"task_id": "t_1", "board": "jarvas-cli"}]
    assert len(recorded) == 1
    assert recorded[0]["board"] == "jarvas-cli"
    assert recorded[0]["task_id"] == "t_1"
    assert str(recorded[0]["error"]) == "handoff proof missing"


def _factory_metadata(revision: str, finding_state: str = "NONE") -> dict:
    return {
        "factory_handoff": {
            "schema": "hermes.factory/handoff-completion/v1",
            "stage_outcome": "PASS",
            "artifact_refs": ["artifact:requirements"],
            "evidence_refs": ["evidence:spec"],
            "evidence_states": ["PASS"],
            "finding_state": finding_state,
            "context_revision": revision,
            "candidate_identity": None,
            "independent_review_state": None,
        }
    }


def test_factory_complete_with_open_findings_is_blocked_before_tool(monkeypatch) -> None:
    plugin = _load_plugin()
    revision = "4" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"
            ),
        ),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": _factory_metadata(revision, "OPEN")},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "finding_state" in result["message"]


def test_factory_complete_with_ready_handoff_is_allowed(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setattr(
        plugin, "validate_factory_repository_precompletion", lambda **kwargs: "a" * 40
    )
    revision = "5" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"
            ),
        ),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": _factory_metadata(revision)},
    )

    assert result is None


def test_factory_complete_with_dirty_repository_is_blocked_before_tool(monkeypatch) -> None:
    plugin = _load_plugin()
    revision = "6" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    task = SimpleNamespace(
        assignee="factory-tdd-red",
        workspace_path="/repo/.worktrees/t_1",
        idempotency_key=(
            f"factory:jarvas-cli:WP-A:TDD_RED:{revision}.stage-contract-v7"
        ),
    )
    monkeypatch.setattr(plugin, "_load_native_task", lambda task_id, board=None: task)

    def reject_repository(**kwargs):
        raise plugin.InstalledRuntimeBindingError("candidate worktree is dirty")

    monkeypatch.setattr(
        plugin, "validate_factory_repository_precompletion", reject_repository, raising=False
    )
    metadata = _factory_metadata(revision)
    metadata["factory_handoff"]["candidate_identity"] = "a" * 40

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": metadata},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "worktree is dirty" in result["message"]


class FakeReworkCoordinator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def schedule(self, **kwargs):
        self.calls.append(("schedule", kwargs))
        if self.fail:
            raise RuntimeError("producer_stage must identify exactly one direct parent stage")
        return "t_rework"

    def activate_pending(self, **kwargs):
        self.calls.append(("activate", kwargs))
        if self.fail:
            raise RuntimeError("pending rework activation failed")
        return "t_rework"


def _rework_reason() -> str:
    return (
        '[factory:upstream-rework/v1] '
        '{"producer_stage":"TDD_RED","finding":"contradictory RED tests",'
        '"evidence_refs":["tests/test_cli_core.py"]}'
    )


def test_factory_dependency_block_schedules_upstream_rework_before_native_block(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "a" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is None
    assert len(coordinator.calls) == 1
    assert coordinator.calls[0][0] == "schedule"
    assert coordinator.calls[0][1]["board"] == "jarvas-cli"
    assert coordinator.calls[0][1]["consumer_task_id"] == "t_impl"
    assert coordinator.calls[0][1]["request"].producer_stage == "TDD_RED"


def test_factory_upstream_rework_requires_dependency_block_kind(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "b" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "capability", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "kind=dependency" in result["message"]
    assert coordinator.calls == []


def test_factory_upstream_rework_schedule_failure_keeps_worker_in_flight(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator(fail=True)
    revision = "c" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "upstream rework validation failed" in result["message"]


def test_rework_completion_relies_on_native_dependency_recompute(monkeypatch) -> None:
    plugin = _load_plugin()
    built = []
    revision = "d" * 64
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key=(
                "factory:jarvas-cli:WP-A~rework-tdd_red-r7-deadbeef1234:"
                f"TDD_RED:{revision}.stage-contract-v10"
            )
        ),
    )
    monkeypatch.setattr(
        plugin,
        "build_installed_completion_coordinator",
        lambda: built.append(True),
    )

    plugin._on_kanban_task_completed(task_id="t_rework", board="jarvas-cli")

    assert built == []


def test_factory_post_block_activates_prepared_rework(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    plugin._on_post_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
        result='{"task_id":"t_impl","run_id":7}',
    )

    assert coordinator.calls[0][0] == "activate"
    assert coordinator.calls[0][1]["board"] == "jarvas-cli"
    assert coordinator.calls[0][1]["consumer_task_id"] == "t_impl"
    assert coordinator.calls[0][1]["request"].producer_stage == "TDD_RED"


def test_factory_upstream_rework_rejects_mismatched_task_context(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "e" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_other", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "task_id" in result["message"]
    assert coordinator.calls == []


def test_factory_upstream_rework_rejects_mismatched_board_context(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "f" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={
            "task_id": "t_impl",
            "board": "other-board",
            "kind": "dependency",
            "reason": _rework_reason(),
        },
    )

    assert result is not None
    assert result["action"] == "block"
    assert "board" in result["message"]
    assert coordinator.calls == []
