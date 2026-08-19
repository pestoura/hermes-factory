import json
from pathlib import Path

import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import InstallOperation


def _contract():
    from hermes_factory.runtime.hermes_install_runtime import (
        CommandResult,
        HermesJarvasInstallRuntime,
    )

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


def _operation(tmp_path: Path):
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"verified exact-head wheel")
    operation = InstallOperation(
        component=RuntimeComponent.FACTORY_PACKAGE,
        action="STAGE_FACTORY_PACKAGE",
        source=str(wheel),
        source_digest="sha256:canonical-digest",
        target="HERMES_RUNTIME_ENV",
    )
    return wheel, operation


def test_package_preflight_refuses_existing_factory_install(tmp_path: Path):
    result_type, runtime_type = _contract()
    _, operation = _operation(tmp_path)
    runner = FakeRunner([result_type(0, "Name: hermes-factory\nVersion: 0.1.0\n", "")])
    runtime = runtime_type(command_runner=runner, python_executable="python-hermes")

    with pytest.raises(RuntimeError, match="already installed"):
        runtime.preflight((operation,))

    assert runner.calls == [
        ("python-hermes", "-m", "pip", "show", "hermes-factory"),
    ]


def test_package_apply_and_rollback_use_verified_wheel_without_dependencies(tmp_path: Path):
    result_type, runtime_type = _contract()
    wheel, operation = _operation(tmp_path)
    runner = FakeRunner(
        [
            result_type(1, "", "WARNING: Package(s) not found: hermes-factory\n"),
            result_type(1, "", "WARNING: Package(s) not found: hermes-factory\n"),
            result_type(0, "Successfully installed hermes-factory-0.1.0\n", ""),
            result_type(0, "Successfully uninstalled hermes-factory-0.1.0\n", ""),
        ]
    )
    runtime = runtime_type(command_runner=runner, python_executable="python-hermes")

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt) == {
        "distribution": "hermes-factory",
        "kind": "FACTORY_PACKAGE_INSTALL",
        "source": str(wheel),
    }

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        ("python-hermes", "-m", "pip", "show", "hermes-factory"),
        ("python-hermes", "-m", "pip", "show", "hermes-factory"),
        (
            "python-hermes",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-input",
            str(wheel),
        ),
        ("python-hermes", "-m", "pip", "uninstall", "-y", "hermes-factory"),
    ]


def test_package_preflight_rejects_wrong_target_and_non_wheel(tmp_path: Path):
    _, runtime_type = _contract()
    source = tmp_path / "factory.tar.gz"
    source.write_bytes(b"not a wheel")
    operation = InstallOperation(
        component=RuntimeComponent.FACTORY_PACKAGE,
        action="STAGE_FACTORY_PACKAGE",
        source=str(source),
        source_digest="sha256:canonical-digest",
        target="OTHER_RUNTIME",
    )
    runner = FakeRunner([])
    runtime = runtime_type(command_runner=runner, python_executable="python-hermes")

    with pytest.raises(RuntimeError, match="Factory package"):
        runtime.preflight((operation,))

    assert runner.calls == []
