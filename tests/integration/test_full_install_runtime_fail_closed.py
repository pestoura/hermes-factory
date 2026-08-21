from pathlib import Path

import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime
from hermes_factory.runtime.install import InstallOperation


class NoCommandRunner:
    def __init__(self) -> None:
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        raise AssertionError("runtime preflight must fail before any external command")


def test_full_phase_p_runtime_preflight_rejects_symbolic_operations_before_any_probe(
    tmp_path: Path,
):
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"verified candidate")
    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n", encoding="utf-8")

    operations = (
        InstallOperation(
            component=RuntimeComponent.FACTORY_PACKAGE,
            action="STAGE_FACTORY_PACKAGE",
            source=str(wheel),
            source_digest="sha256:canonical-digest",
            target="HERMES_RUNTIME_ENV",
        ),
        InstallOperation(
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
        ),
        InstallOperation(
            component=RuntimeComponent.FACTORY_SKILLS,
            action="INSTALL_FACTORY_SKILLS_WITH_PROFILE_DISTRIBUTIONS",
            source="canonical factory-* Skill artifacts",
            target="PROFILE_SCOPED_SKILLS",
        ),
        InstallOperation(
            component=RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
            action="APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
            target="HERMES_KANBAN",
        ),
        InstallOperation(
            component=RuntimeComponent.GATEWAY_HITL_ADAPTER,
            action="REGISTER_GATEWAY_HITL_ADAPTER",
            source="hermes_factory.adapters.hermes_gateway",
            target="HERMES_GATEWAY",
        ),
        InstallOperation(
            component=RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION,
            action="REGISTER_NORTHBOUND_CONTROL_INTEGRATION",
            source=str(tmp_path / "factory-northbound.yaml"),
            target="HERMES_MCP_BRIDGE",
        ),
    )
    runner = NoCommandRunner()
    runtime = HermesJarvasInstallRuntime(command_runner=runner)

    with pytest.raises(RuntimeError, match="unsupported install operation"):
        runtime.preflight(operations)

    assert runner.calls == []
