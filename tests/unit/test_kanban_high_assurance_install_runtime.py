import json

import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.hermes_install_runtime import (
    CommandResult,
    HermesJarvasInstallRuntime,
)
from hermes_factory.runtime.install import InstallOperation


class FakeRunner:
    def __init__(self, responses: list[CommandResult]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError("unexpected command execution")
        return self.responses.pop(0)


def _operation() -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
        action="APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
        target="HERMES_KANBAN",
    )


def test_kanban_policy_preflight_is_structural_and_non_mutating() -> None:
    runner = FakeRunner([])
    runtime = HermesJarvasInstallRuntime(command_runner=runner)

    runtime.preflight((_operation(),))

    assert runner.calls == []


def test_kanban_policy_already_false_is_noop_and_preserves_existing_state() -> None:
    runner = FakeRunner([CommandResult(0, "false\n", "")])
    runtime = HermesJarvasInstallRuntime(command_runner=runner)
    operation = _operation()

    receipt = runtime.apply(operation)

    assert json.loads(receipt) == {
        "changed": "false",
        "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
        "previous": "false",
    }
    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
    ]

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
    ]


def test_kanban_policy_true_is_set_false_verified_and_restored_on_rollback() -> None:
    runner = FakeRunner(
        [
            CommandResult(0, "true\n", ""),
            CommandResult(0, "Set kanban.auto_decompose = false\n", ""),
            CommandResult(0, "false\n", ""),
            CommandResult(0, "Set kanban.auto_decompose = true\n", ""),
            CommandResult(0, "true\n", ""),
        ]
    )
    runtime = HermesJarvasInstallRuntime(command_runner=runner)
    operation = _operation()

    receipt = runtime.apply(operation)

    assert json.loads(receipt) == {
        "changed": "true",
        "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
        "previous": "true",
    }
    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "false"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
    ]

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "false"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "true"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
    ]


def test_kanban_policy_rejects_non_boolean_resolved_value() -> None:
    runner = FakeRunner([CommandResult(0, '"false"\n', "")])
    runtime = HermesJarvasInstallRuntime(command_runner=runner)

    with pytest.raises(TypeError, match="boolean"):
        runtime.apply(_operation())


def test_kanban_policy_compensates_when_post_mutation_verification_fails() -> None:
    runner = FakeRunner(
        [
            CommandResult(0, "true\n", ""),
            CommandResult(0, "Set kanban.auto_decompose = false\n", ""),
            CommandResult(2, "", "config read failed"),
            CommandResult(0, "Set kanban.auto_decompose = true\n", ""),
            CommandResult(0, "true\n", ""),
        ]
    )
    runtime = HermesJarvasInstallRuntime(command_runner=runner)

    with pytest.raises(RuntimeError, match="config read failed with exit code 2"):
        runtime.apply(_operation())

    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "false"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "true"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
    ]


def test_kanban_policy_surfaces_unknown_state_when_compensation_fails() -> None:
    runner = FakeRunner(
        [
            CommandResult(0, "true\n", ""),
            CommandResult(0, "Set kanban.auto_decompose = false\n", ""),
            CommandResult(2, "", "config read failed"),
            CommandResult(3, "", "restore failed"),
        ]
    )
    runtime = HermesJarvasInstallRuntime(command_runner=runner)

    with pytest.raises(RuntimeError, match="compensation failed.*state is unknown"):
        runtime.apply(_operation())

    assert runner.calls == [
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "false"),
        ("hermes", "config", "get", "kanban.auto_decompose", "--json"),
        ("hermes", "config", "set", "kanban.auto_decompose", "true"),
    ]
