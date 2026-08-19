import json
from pathlib import Path

import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import InstallOperation


def _contract():
    try:
        from hermes_factory.runtime.hermes_install_runtime import (
            CommandResult,
            HermesJarvasInstallRuntime,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("Hermes/Jarvas install runtime adapter is not implemented") from exc
    return CommandResult, HermesJarvasInstallRuntime


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError("unexpected command execution")
        return self.responses.pop(0)


def test_runtime_preflight_rejects_unsupported_operation_before_any_command(tmp_path: Path):
    result_type, runtime_type = _contract()
    runner = FakeRunner([result_type(0, "", "")])
    runtime = runtime_type(command_runner=runner)
    unsupported = InstallOperation(
        component=RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
        action="APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
        target="HERMES_KANBAN",
    )

    with pytest.raises(RuntimeError, match="unsupported install operation"):
        runtime.preflight((unsupported,))

    assert runner.calls == []


def test_runtime_applies_and_rolls_back_native_profile_install(tmp_path: Path):
    result_type, runtime_type = _contract()
    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n", encoding="utf-8")
    operation = InstallOperation(
        component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
        action="INSTALL_NATIVE_PROFILE_DISTRIBUTION",
        argv=(
            "hermes",
            "profile",
            "install",
            str(profile),
            "--name",
            "factory-orchestrator",
            "-y",
        ),
        source=str(profile),
        target="HERMES_HOME/profiles/factory-orchestrator",
    )
    runner = FakeRunner(
        [
            result_type(0, "Profile installed: factory-orchestrator\n", ""),
            result_type(0, "Deleted profile: factory-orchestrator\n", ""),
        ]
    )
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload["kind"] == "PROFILE_INSTALL"
    assert payload["profile_id"] == "factory-orchestrator"

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        operation.argv,
        ("hermes", "profile", "delete", "factory-orchestrator", "-y"),
    ]


def test_runtime_applies_and_rolls_back_native_profile_cron(tmp_path: Path):
    result_type, runtime_type = _contract()
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="CREATE_NATIVE_PROFILE_CRON_DUTY",
        argv=(
            "hermes",
            "-p",
            "factory-release-manager",
            "cron",
            "create",
            "0 9 * * 1",
            "Run release review",
            "--name",
            "weekly-release-review",
        ),
        target="HERMES_PROFILE/factory-release-manager/cron",
    )
    runner = FakeRunner(
        [
            result_type(
                0,
                "Created job: job-123\n  Name: weekly-release-review\n",
                "",
            ),
            result_type(0, "Removed job: job-123\n", ""),
        ]
    )
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload == {
        "job_id": "job-123",
        "kind": "PROFILE_CRON_CREATE",
        "profile_id": "factory-release-manager",
    }

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        operation.argv,
        ("hermes", "-p", "factory-release-manager", "cron", "remove", "job-123"),
    ]


def test_runtime_fails_if_cron_success_output_has_no_job_id():
    result_type, runtime_type = _contract()
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="CREATE_NATIVE_PROFILE_CRON_DUTY",
        argv=(
            "hermes",
            "-p",
            "factory-release-manager",
            "cron",
            "create",
            "0 9 * * 1",
            "Run release review",
            "--name",
            "weekly-release-review",
        ),
        target="HERMES_PROFILE/factory-release-manager/cron",
    )
    runner = FakeRunner([result_type(0, "Created successfully\n", "")])
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    with pytest.raises(RuntimeError, match="job id"):
        runtime.apply(operation)


def test_runtime_empty_cron_plan_is_explicit_noop_with_no_command():
    _, runtime_type = _contract()
    runner = FakeRunner([])
    runtime = runtime_type(command_runner=runner)
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
        target="HERMES_PROFILE_CRON",
    )

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt) == {"kind": "EMPTY_CRON_PLAN"}
    runtime.rollback(operation, receipt)
    assert runner.calls == []
