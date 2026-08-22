from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime
from hermes_factory.runtime.install import InstallOperation


class NoCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: tuple[str, ...]):
        self.calls.append(argv)
        raise AssertionError("northbound binding verification must not execute external commands")


def _binding(tmp_path: Path, *, default_enabled: bool = False) -> Path:
    path = tmp_path / "factory-northbound.yaml"
    path.write_text(
        "schema: hermes.factory/runtime-component-binding/v1\n"
        "component: NORTHBOUND_CONTROL_INTEGRATION\n"
        "repository: pestoura/hermes-mcp-bridge\n"
        "pull_request: 111\n"
        "candidate_sha: 2bc624f4f91dce4cdb13f904647bf41bffa36941\n"
        "verification_state: PASS\n"
        f"default_enabled: {str(default_enabled).lower()}\n"
        "internal_factory_ipc: false\n"
        "mutation_execution: false\n"
        "production_entrypoint: hermes_mcp_bridge.http_runner\n"
        "tools:\n"
        "  - factory_acceptance\n"
        "  - factory_evidence\n"
        "  - factory_protected_mutation_intent\n"
        "  - factory_status\n"
        "protected_actions:\n"
        "  - ACTIVATE_PROFILE\n"
        "  - ACTIVATE_SKILL\n"
        "  - MERGE_PR\n"
        "  - RELEASE\n",
        encoding="utf-8",
    )
    return path


def _operation(binding: Path, *, action: str = "VERIFY_NORTHBOUND_CONTROL_BINDING") -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION,
        action=action,
        source=str(binding),
        source_digest=digest_artifact(binding),
        target="HERMES_MCP_BRIDGE",
    )


def test_runtime_verifies_safe_northbound_binding_without_external_mutation(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    runner = NoCommandRunner()
    runtime = HermesJarvasInstallRuntime(command_runner=runner)
    operation = _operation(binding)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)

    assert receipt == '{"kind":"NORTHBOUND_CONTROL_BINDING_VERIFIED"}'
    assert runner.calls == []

    runtime.rollback(operation, receipt)
    assert runner.calls == []


def test_runtime_rejects_unsafe_northbound_binding(tmp_path: Path) -> None:
    runtime = HermesJarvasInstallRuntime(command_runner=NoCommandRunner())
    with pytest.raises(RuntimeError, match="default_enabled"):
        runtime.preflight((_operation(_binding(tmp_path, default_enabled=True)),))


def test_runtime_rejects_fictitious_northbound_registration_action(tmp_path: Path) -> None:
    runtime = HermesJarvasInstallRuntime(command_runner=NoCommandRunner())
    with pytest.raises(RuntimeError, match="unsupported"):
        runtime.preflight((_operation(_binding(tmp_path), action="REGISTER_NORTHBOUND_CONTROL_INTEGRATION"),))
