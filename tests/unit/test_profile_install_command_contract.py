from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder
from hermes_factory.runtime.package_candidate import (
    build_package_candidate_manifest,
    load_package_candidate,
)


def test_profile_install_command_is_non_interactive_exact_name_and_never_force(tmp_path: Path):
    factory_sha = "f" * 40
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"candidate")
    manifest = tmp_path / "factory-package.json"
    build_package_candidate_manifest(
        wheel_path=wheel, candidate_sha=factory_sha, output_path=manifest
    )
    candidate = load_package_candidate(
        manifest_path=manifest,
        wheel_path=wheel,
        expected_candidate_sha=factory_sha,
    )

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

    plan = ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=factory_sha,
        factory_package_candidate=candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states={component: AdmissionEvidenceState.PASS for component in RuntimeComponent},
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )

    operation = next(
        op for op in plan.operations
        if op.component is RuntimeComponent.PROFILE_DISTRIBUTIONS
    )
    assert operation.argv == (
        "hermes",
        "profile",
        "install",
        str(profile),
        "--name",
        "factory-orchestrator",
        "-y",
    )
    assert "--force" not in operation.argv
