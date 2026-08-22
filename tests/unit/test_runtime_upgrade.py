import json
from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import InstallOperation
from hermes_factory.runtime.package_candidate import FactoryPackageCandidate


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError("unexpected command execution")
        return self.responses.pop(0)


class FakePackageProbe:
    def __init__(self, *states):
        self.states = list(states)
        self.calls = 0

    def current(self):
        self.calls += 1
        if not self.states:
            raise AssertionError("unexpected package probe")
        return self.states.pop(0)


def _candidate(root: Path, sha: str, payload: bytes) -> FactoryPackageCandidate:
    root.mkdir(parents=True)
    wheel = root / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(payload)
    return FactoryPackageCandidate(
        candidate_sha=sha,
        wheel_path=wheel,
        filename=wheel.name,
        artifact_digest=digest_artifact(wheel),
        content_sha256=__import__("hashlib").sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def _package_operation(candidate: FactoryPackageCandidate) -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.FACTORY_PACKAGE,
        action="STAGE_FACTORY_PACKAGE",
        source=str(candidate.wheel_path),
        source_digest=candidate.artifact_digest,
        target="HERMES_RUNTIME_ENV",
    )


def test_verified_package_upgrade_and_rollback(tmp_path: Path):
    from hermes_factory.runtime.hermes_install_runtime import (
        CommandResult,
        HermesJarvasInstallRuntime,
    )

    old = _candidate(tmp_path / "old", "1" * 40, b"old-wheel")
    new = _candidate(tmp_path / "new", "2" * 40, b"new-wheel")
    probe = FakePackageProbe(old, old, new, old)
    runner = FakeRunner([
        CommandResult(0, "upgraded\n", ""),
        CommandResult(0, "restored\n", ""),
    ])
    runtime = HermesJarvasInstallRuntime(
        command_runner=runner,
        python_executable="python-hermes",
        factory_package_probe=probe,
    )
    operation = _package_operation(new)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt)["kind"] == "FACTORY_PACKAGE_UPGRADE"
    runtime.rollback(operation, receipt)
    assert probe.calls == 4
    assert runner.calls == [
        (
            "python-hermes", "-m", "pip", "install", "--force-reinstall",
            "--no-deps", "--no-input", str(new.wheel_path),
        ),
        (
            "python-hermes", "-m", "pip", "install", "--force-reinstall",
            "--no-deps", "--no-input", str(old.wheel_path),
        ),
    ]


def test_package_upgrade_requires_rollback_wheel_to_still_exist(tmp_path: Path):
    from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime

    old = _candidate(tmp_path / "old", "1" * 40, b"old-wheel")
    old.wheel_path.unlink()
    new = _candidate(tmp_path / "new", "2" * 40, b"new-wheel")
    runtime = HermesJarvasInstallRuntime(
        command_runner=FakeRunner([]),
        factory_package_probe=FakePackageProbe(old),
    )

    with pytest.raises(RuntimeError, match="rollback package"):
        runtime.preflight((_package_operation(new),))


def _profile_operation(source: Path) -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
        action="INSTALL_NATIVE_PROFILE_DISTRIBUTION",
        argv=(
            "hermes", "profile", "install", str(source), "--name",
            "factory-orchestrator", "-y",
        ),
        source=str(source),
        source_digest=digest_artifact(source),
        target="HERMES_HOME/profiles/factory-orchestrator",
    )


def test_existing_identical_profile_distribution_is_reused(tmp_path: Path):
    from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime

    home = tmp_path / "home"
    source = tmp_path / "profile"
    installed = home / "profiles" / "factory-orchestrator"
    source.mkdir(parents=True)
    installed.mkdir(parents=True)
    (source / "distribution.yaml").write_text("name: factory-orchestrator\n")
    (installed / "distribution.yaml").write_text("name: factory-orchestrator\n")
    (installed / "state.db").write_text("mutable-state")
    runtime = HermesJarvasInstallRuntime(
        command_runner=FakeRunner([]), hermes_home=home,
    )
    operation = _profile_operation(source)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt) == {
        "kind": "PROFILE_REUSE",
        "profile_id": "factory-orchestrator",
        "source_digest": operation.source_digest,
    }
    runtime.rollback(operation, receipt)
    assert (installed / "state.db").read_text() == "mutable-state"


def test_profile_managed_drift_blocks_upgrade_before_mutation(tmp_path: Path):
    from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime

    home = tmp_path / "home"
    source = tmp_path / "profile"
    installed = home / "profiles" / "factory-orchestrator"
    source.mkdir(parents=True)
    installed.mkdir(parents=True)
    (source / "distribution.yaml").write_text("name: factory-orchestrator\n")
    (installed / "distribution.yaml").write_text("name: drifted\n")
    runtime = HermesJarvasInstallRuntime(command_runner=FakeRunner([]), hermes_home=home)

    with pytest.raises(RuntimeError, match="managed distribution drift"):
        runtime.preflight((_profile_operation(source),))


def _dashboard_operation(source: Path) -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="REGISTER_DASHBOARD_PLUGIN",
        source=str(source),
        source_digest=digest_artifact(source),
        target="HERMES_HOME/plugins/hermes-factory",
    )


def test_dashboard_upgrade_is_backed_up_and_restorable(tmp_path: Path):
    from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime

    home = tmp_path / "home"
    source = tmp_path / "new-plugin"
    target = home / "plugins" / "hermes-factory"
    (source / "dashboard").mkdir(parents=True)
    (target / "dashboard").mkdir(parents=True)
    (source / "dashboard" / "manifest.json").write_text('{"version":"new"}\n')
    (target / "dashboard" / "manifest.json").write_text('{"version":"old"}\n')
    old = _candidate(tmp_path / "old-package", "1" * 40, b"old-wheel")
    runtime = HermesJarvasInstallRuntime(
        command_runner=FakeRunner([]),
        hermes_home=home,
        factory_package_probe=FakePackageProbe(old),
    )
    operation = _dashboard_operation(source)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt)["kind"] == "DASHBOARD_PLUGIN_UPGRADE"
    assert (target / "dashboard" / "manifest.json").read_text() == '{"version":"new"}\n'
    backup = home / "factory" / "dashboard-plugin-catalog" / old.candidate_sha
    assert (backup / "dashboard" / "manifest.json").read_text() == '{"version":"old"}\n'

    runtime.rollback(operation, receipt)
    assert (target / "dashboard" / "manifest.json").read_text() == '{"version":"old"}\n'


def test_subprocess_package_probe_loads_exact_installed_candidate(tmp_path: Path):
    import json as json_module
    from hermes_factory.runtime.hermes_install_runtime import (
        CommandResult, SubprocessFactoryPackageProbe,
    )

    root = tmp_path / ("factory-package-candidate-" + "3" * 40)
    candidate = _candidate(root, "3" * 40, b"installed")
    manifest = candidate.wheel_path.parent / "factory-package.json"
    manifest.write_text(json_module.dumps({
        "schema": "hermes.factory/package-candidate/v2",
        "candidate_sha": candidate.candidate_sha,
        "filename": candidate.filename,
        "artifact_digest": candidate.artifact_digest,
        "content_sha256": candidate.content_sha256,
        "size_bytes": candidate.size_bytes,
    }))
    direct_url = json_module.dumps({"url": candidate.wheel_path.as_uri()})
    runner = FakeRunner([
        CommandResult(0, "Name: hermes-factory\n", ""),
        CommandResult(0, direct_url, ""),
    ])
    observed = SubprocessFactoryPackageProbe(runner, "python-hermes").current()
    assert observed is not None
    assert observed.candidate_sha == candidate.candidate_sha
    assert observed.artifact_digest == candidate.artifact_digest
