from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder


def _passing_components():
    return {component: AdmissionEvidenceState.PASS for component in RuntimeComponent}


def _surfaces(tmp_path: Path):
    package = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    package.write_bytes(b"exact candidate package")

    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n", encoding="utf-8")

    dashboard = tmp_path / "dashboard-plugin" / "hermes-factory"
    (dashboard / "dashboard").mkdir(parents=True)
    (dashboard / "dashboard" / "manifest.json").write_text(
        '{"name":"hermes-factory","entry":"dist/index.js"}\n', encoding="utf-8"
    )

    northbound = tmp_path / "factory-northbound.yaml"
    northbound.write_text("component: NORTHBOUND_CONTROL_INTEGRATION\n", encoding="utf-8")
    return package, profile, dashboard, northbound


def _build(tmp_path: Path, expected_package_digest: str):
    package, profile, dashboard, northbound = _surfaces(tmp_path)
    plan = ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        factory_package_source=package,
        expected_factory_package_digest=expected_package_digest,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=_passing_components(),
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )
    return package, plan


def test_controlled_install_binds_factory_package_to_exact_artifact_digest(tmp_path: Path):
    package = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    package.write_bytes(b"exact candidate package")
    expected = digest_artifact(package)
    package.unlink()

    actual_package, plan = _build(tmp_path, expected)

    assert plan.ready_for_controlled_execution is True
    package_operation = next(
        operation
        for operation in plan.operations
        if operation.component is RuntimeComponent.FACTORY_PACKAGE
    )
    assert package_operation.source == str(actual_package)
    assert package_operation.target == "HERMES_RUNTIME_ENV"


def test_controlled_install_blocks_factory_package_digest_drift(tmp_path: Path):
    package, profile, dashboard, northbound = _surfaces(tmp_path)
    expected = digest_artifact(package)
    package.write_bytes(b"changed after package identity was recorded")

    plan = ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        factory_package_source=package,
        expected_factory_package_digest=expected,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=_passing_components(),
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )

    assert plan.ready_for_controlled_execution is False
    assert plan.execution_state == "BLOCKED"
    assert any("Factory package digest drift" in blocker for blocker in plan.blockers)
