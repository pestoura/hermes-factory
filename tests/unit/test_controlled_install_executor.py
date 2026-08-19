from dataclasses import replace
from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder
from hermes_factory.runtime.package_candidate import (
    build_package_candidate_manifest,
    load_package_candidate,
)

_FACTORY_SHA = "f" * 40


def _contract():
    try:
        from hermes_factory.runtime.install_execution import (
            InstallExecutionAuthorization,
            InstallExecutionError,
            InstallExecutor,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("controlled install executor is not implemented") from exc
    return InstallExecutionAuthorization, InstallExecutionError, InstallExecutor


def _ready_plan(tmp_path: Path):
    package = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    package.write_bytes(b"exact candidate package")
    package_manifest = tmp_path / "factory-package.json"
    build_package_candidate_manifest(
        wheel_path=package,
        candidate_sha=_FACTORY_SHA,
        output_path=package_manifest,
    )
    candidate = load_package_candidate(
        manifest_path=package_manifest,
        wheel_path=package,
        expected_candidate_sha=_FACTORY_SHA,
    )

    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text(
        "name: factory-orchestrator\n", encoding="utf-8"
    )
    dashboard = tmp_path / "dashboard-plugin" / "hermes-factory"
    (dashboard / "dashboard").mkdir(parents=True)
    (dashboard / "dashboard" / "manifest.json").write_text(
        '{"name":"hermes-factory","entry":"dist/index.js"}\n', encoding="utf-8"
    )
    northbound = tmp_path / "factory-northbound.yaml"
    northbound.write_text(
        "component: NORTHBOUND_CONTROL_INTEGRATION\n", encoding="utf-8"
    )
    components = {
        component: AdmissionEvidenceState.PASS for component in RuntimeComponent
    }
    return ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={
            "factory-orchestrator": digest_artifact(profile)
        },
        profile_eval_states={
            "factory-orchestrator": AdmissionEvidenceState.PASS
        },
        skill_eval_states={
            "factory-reading-project-truth": AdmissionEvidenceState.PASS
        },
        component_states=components,
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )


class FakeRuntime:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.fail_at = fail_at
        self.applied = []
        self.rolled_back = []

    def apply(self, operation):
        index = len(self.applied)
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("synthetic install failure")
        receipt = f"receipt-{index}"
        self.applied.append((operation, receipt))
        return receipt

    def rollback(self, operation, receipt):
        self.rolled_back.append((operation, receipt))


def _authorization(plan):
    authorization_type, _, _ = _contract()
    return authorization_type(
        plan_digest=plan.digest,
        approved_by="owner:pestoura",
        evidence_ref="approval://phase-p/install/1",
    )


def test_executor_refuses_blocked_plan_without_touching_runtime(tmp_path: Path):
    _, error_type, executor_type = _contract()
    plan = _ready_plan(tmp_path)
    blocked = replace(
        plan,
        blockers=("Profile factory-orchestrator=NOT_RUN",),
        execution_state="BLOCKED",
        ready_for_controlled_execution=False,
    )
    runtime = FakeRuntime()

    with pytest.raises(error_type, match="not READY"):
        executor_type(runtime).execute(blocked, _authorization(blocked))

    assert runtime.applied == []
    assert runtime.rolled_back == []


def test_executor_requires_digest_bound_explicit_authorization(tmp_path: Path):
    authorization_type, error_type, executor_type = _contract()
    plan = _ready_plan(tmp_path)
    runtime = FakeRuntime()

    with pytest.raises(error_type, match="plan digest"):
        executor_type(runtime).execute(
            plan,
            authorization_type(
                plan_digest="0" * 64,
                approved_by="owner:pestoura",
                evidence_ref="approval://phase-p/install/1",
            ),
        )

    assert runtime.applied == []


def test_executor_applies_every_operation_only_after_authorization(tmp_path: Path):
    _, _, executor_type = _contract()
    plan = _ready_plan(tmp_path)
    runtime = FakeRuntime()

    report = executor_type(runtime).execute(plan, _authorization(plan))

    assert report.state == "PASS"
    assert report.plan_digest == plan.digest
    assert report.applied_count == len(plan.operations)
    assert report.rolled_back_count == 0
    assert len(runtime.applied) == len(plan.operations)
    assert runtime.rolled_back == []
    assert report.execute is True
    assert len(report.digest) == 64


def test_executor_rolls_back_applied_operations_in_reverse_order_on_failure(
    tmp_path: Path,
):
    _, _, executor_type = _contract()
    plan = _ready_plan(tmp_path)
    runtime = FakeRuntime(fail_at=3)

    report = executor_type(runtime).execute(plan, _authorization(plan))

    assert report.state == "ROLLED_BACK"
    assert report.applied_count == 3
    assert report.rolled_back_count == 3
    assert "synthetic install failure" in report.failure
    assert [operation for operation, _ in runtime.rolled_back] == [
        operation for operation, _ in reversed(runtime.applied)
    ]


def test_executor_never_treats_empty_approval_provenance_as_authorized(tmp_path: Path):
    authorization_type, error_type, executor_type = _contract()
    plan = _ready_plan(tmp_path)
    runtime = FakeRuntime()

    with pytest.raises(error_type, match="approval provenance"):
        executor_type(runtime).execute(
            plan,
            authorization_type(
                plan_digest=plan.digest,
                approved_by=" ",
                evidence_ref="",
            ),
        )

    assert runtime.applied == []
