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
