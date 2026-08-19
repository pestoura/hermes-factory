from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.package_candidate import (
    build_package_candidate_manifest,
    load_package_candidate,
)

_FACTORY_SHA = "f" * 40


def _contract():
    try:
        from hermes_factory.runtime.install import (
            ControlledInstallPlanBuilder,
            InstallPlanError,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("Phase P controlled install plan is not implemented") from exc
    return ControlledInstallPlanBuilder, InstallPlanError


def _artifacts(tmp_path: Path):
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


def _package_candidate(package: Path):
    manifest = package.with_name("factory-package.json")
    build_package_candidate_manifest(
        wheel_path=package,
        candidate_sha=_FACTORY_SHA,
        output_path=manifest,
    )
    return load_package_candidate(
        manifest_path=manifest,
        wheel_path=package,
        expected_candidate_sha=_FACTORY_SHA,
    )


def _passing_components():
    return {component: AdmissionEvidenceState.PASS for component in RuntimeComponent}


def test_controlled_install_plan_is_ready_only_with_exact_sha_and_all_pass_evidence(tmp_path: Path):
    builder_type, _ = _contract()
    package, profile, dashboard, northbound = _artifacts(tmp_path)
    candidate = _package_candidate(package)
    profile_digest = digest_artifact(profile)
    cron_plan = NativeCronPlanBuilder().build({})

    plan = builder_type().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": profile_digest},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=_passing_components(),
        cron_plan=cron_plan,
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )

    assert plan.ready_for_controlled_execution is True
    assert plan.factory_candidate_sha == _FACTORY_SHA
    assert plan.execute is False
    assert plan.execution_state == "READY"
    assert plan.blockers == ()
    assert len(plan.digest) == 64
    assert {operation.component for operation in plan.operations} == set(RuntimeComponent)
    assert any(
        operation.argv == ("hermes", "profile", "install", str(profile))
        for operation in plan.operations
    )
    package_operation = next(
        operation
        for operation in plan.operations
        if operation.component is RuntimeComponent.FACTORY_PACKAGE
    )
    assert package_operation.source == str(package)
    assert package_operation.source_digest == candidate.artifact_digest
    dashboard_operation = next(
        operation
        for operation in plan.operations
        if operation.component is RuntimeComponent.DASHBOARD_PLUGIN
    )
    assert dashboard_operation.source == str(dashboard)
    assert dashboard_operation.target == "HERMES_HOME/plugins/hermes-factory"


def test_controlled_install_plan_collects_not_run_blocked_and_sha_mismatch_without_execution(tmp_path: Path):
    builder_type, _ = _contract()
    package, profile, dashboard, northbound = _artifacts(tmp_path)
    candidate = _package_candidate(package)
    components = _passing_components()
    components[RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION] = AdmissionEvidenceState.BLOCKED

    plan = builder_type().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="b" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.NOT_RUN},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.NOT_RUN},
        component_states=components,
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )

    assert plan.ready_for_controlled_execution is False
    assert plan.execute is False
    assert plan.execution_state == "BLOCKED"
    assert any("exact Hermes SHA" in blocker for blocker in plan.blockers)
    assert "Profile factory-orchestrator=NOT_RUN" in plan.blockers
    assert "Skill factory-reading-project-truth=NOT_RUN" in plan.blockers
    assert "Component NORTHBOUND_CONTROL_INTEGRATION=BLOCKED" in plan.blockers


def test_controlled_install_plan_detects_profile_artifact_digest_drift(tmp_path: Path):
    builder_type, _ = _contract()
    package, profile, dashboard, northbound = _artifacts(tmp_path)
    candidate = _package_candidate(package)
    expected = digest_artifact(profile)
    (profile / "SOUL.md").write_text("changed after eval\n", encoding="utf-8")

    plan = builder_type().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": expected},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=_passing_components(),
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )

    assert plan.ready_for_controlled_execution is False
    assert any("digest drift" in blocker for blocker in plan.blockers)


def test_controlled_install_plan_rejects_missing_install_surfaces_and_secret_like_paths(tmp_path: Path):
    builder_type, error_type = _contract()
    package, profile, _, northbound = _artifacts(tmp_path)
    candidate = _package_candidate(package)
    unsafe_dashboard = tmp_path / ".env" / "hermes-factory"
    unsafe_dashboard.mkdir(parents=True)

    with pytest.raises(error_type, match="secret"):
        builder_type().build(
            accepted_hermes_sha="a" * 40,
            observed_hermes_sha="a" * 40,
            expected_factory_candidate_sha=_FACTORY_SHA,
            factory_package_candidate=candidate,
            profile_artifacts={"factory-orchestrator": profile},
            expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
            profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
            skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
            component_states=_passing_components(),
            cron_plan=NativeCronPlanBuilder().build({}),
            dashboard_plugin_source=unsafe_dashboard,
            gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
            northbound_binding_source=northbound,
        )
