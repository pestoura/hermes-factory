import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import ControlledInstallPlan, InstallOperation
from hermes_factory.runtime.install_execution import (
    InstallExecutionAuthorization,
    InstallExecutionError,
    InstallExecutor,
)


class RejectingRuntime:
    def __init__(self) -> None:
        self.preflight_calls = 0
        self.apply_calls = 0

    def preflight(self, operations):
        self.preflight_calls += 1
        raise RuntimeError("unsupported install operation")

    def apply(self, operation):
        self.apply_calls += 1
        return "must-not-run"

    def rollback(self, operation, receipt):
        raise AssertionError("rollback must not run when preflight fails")


def test_executor_runs_runtime_preflight_before_first_mutation():
    plan = ControlledInstallPlan(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        factory_candidate_sha="f" * 40,
        operations=(
            InstallOperation(
                component=RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
                action="UNSUPPORTED_FOR_TEST",
                target="HERMES_KANBAN",
            ),
        ),
        blockers=(),
        execution_state="READY",
        ready_for_controlled_execution=True,
        execute=False,
    )
    authorization = InstallExecutionAuthorization(
        plan_digest=plan.digest,
        approved_by="owner:pestoura",
        evidence_ref="approval://phase-p/runtime-preflight",
    )
    runtime = RejectingRuntime()

    with pytest.raises(InstallExecutionError, match="runtime preflight"):
        InstallExecutor(runtime).execute(plan, authorization)

    assert runtime.preflight_calls == 1
    assert runtime.apply_calls == 0
