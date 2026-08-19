from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder
from hermes_factory.runtime.install_execution import (
    InstallExecutionAuthorization,
    InstallExecutionError,
    InstallExecutor,
)


class RecordingRuntime:
    def __init__(self) -> None:
        self.applied = []

    def apply(self, operation):
        self.applied.append(operation)
        return f"receipt-{len(self.applied)}"

    def rollback(self, operation, receipt):
        raise AssertionError("rollback must not be needed before the first mutation")


def _ready_plan(tmp_path: Path):
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

    plan = ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        factory_package_source=package,
        expected_factory_package_digest=digest_artifact(package),
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
    return {
        "package": package,
        "profile": profile / "distribution.yaml",
        "dashboard": dashboard / "dashboard" / "manifest.json",
        "northbound": northbound,
    }, plan


@pytest.mark.parametrize("source_name", ["package", "profile", "dashboard", "northbound"])
def test_install_executor_revalidates_all_local_source_identity_before_first_mutation(
    tmp_path: Path,
    source_name: str,
):
    sources, plan = _ready_plan(tmp_path)
    authorization = InstallExecutionAuthorization(
        plan_digest=plan.digest,
        approved_by="owner:pestoura",
        evidence_ref="approval://phase-p/install/source-identity",
    )
    source = sources[source_name]
    if source_name == "profile":
        source.write_text("name: tampered-after-authorization\n", encoding="utf-8")
    elif source_name == "dashboard":
        source.write_text('{"name":"tampered"}\n', encoding="utf-8")
    elif source_name == "northbound":
        source.write_text("component: TAMPERED\n", encoding="utf-8")
    else:
        source.write_bytes(b"tampered after authorization")
    runtime = RecordingRuntime()

    with pytest.raises(InstallExecutionError, match="source digest"):
        InstallExecutor(runtime).execute(plan, authorization)

    assert runtime.applied == []
