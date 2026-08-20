from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.hermes_install_runtime import (
    CommandResult,
    HermesJarvasInstallRuntime,
)
from hermes_factory.runtime.install import InstallOperation


class _Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(argv)
        return CommandResult(returncode=0, stdout="", stderr="")


def _operation() -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.GATEWAY_HITL_ADAPTER,
        action="VERIFY_GATEWAY_HITL_BINDING",
        source="hermes_factory.adapters.hermes_gateway",
        target="HERMES_GATEWAY",
    )


def test_runtime_verifies_gateway_hitl_binding_in_target_python() -> None:
    runner = _Runner()
    runtime = HermesJarvasInstallRuntime(
        command_runner=runner,
        python_executable="/runtime/python",
    )
    operation = _operation()

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)

    assert runner.calls == [
        (
            "/runtime/python",
            "-c",
            "from hermes_factory.adapters.hermes_gateway import "
            "HermesGatewayHITLBinding; assert callable(HermesGatewayHITLBinding)",
        )
    ]
    assert receipt == '{"kind":"GATEWAY_HITL_BINDING_VERIFIED"}'

    runtime.rollback(operation, receipt)
    assert len(runner.calls) == 1


def test_runtime_rejects_fictitious_gateway_registration_action() -> None:
    runtime = HermesJarvasInstallRuntime(command_runner=_Runner())
    operation = InstallOperation(
        component=RuntimeComponent.GATEWAY_HITL_ADAPTER,
        action="REGISTER_GATEWAY_HITL_ADAPTER",
        source="hermes_factory.adapters.hermes_gateway",
        target="HERMES_GATEWAY",
    )

    try:
        runtime.preflight((operation,))
    except RuntimeError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("fictitious Gateway registration must remain unsupported")
