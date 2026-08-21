from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlanBuilder
from hermes_factory.runtime.install import ControlledInstallPlanBuilder
from hermes_factory.runtime.package_candidate import (
    build_package_candidate_manifest,
    load_package_candidate,
)
from hermes_factory.runtime.skill_catalog_candidate import build_skill_catalog_candidate

_FACTORY_SHA = "f" * 40


def _passing_components():
    return {component: AdmissionEvidenceState.PASS for component in RuntimeComponent}


def _skill_candidate(tmp_path: Path):
    source = tmp_path / "skills" / "core" / "reading-project-truth"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: factory-reading-project-truth\ndescription: Test Skill\n---\n# Test\n",
        encoding="utf-8",
    )
    registry = {
        "schema": "hermes.factory/skills/v1.2",
        "registry": {
            "core": ["factory-reading-project-truth"],
            "control_workforce": [],
            "product_architecture": [],
            "documentation": [],
            "engineering_quality": [],
            "security_assurance": [],
            "governance_operations": [],
            "proposed_v1_2_skills": {},
            "legacy_source_aliases": {},
            "superseded_skill_concepts": {},
            "consumers": {},
        },
    }
    return build_skill_catalog_candidate(
        source_root=tmp_path / "skills",
        registry_document=registry,
        candidate_sha=_FACTORY_SHA,
        output_root=tmp_path / "skill-candidate",
    )


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


def _candidate(package: Path):
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


def _build(package, candidate, skill_candidate, profile, dashboard, northbound):
    return ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=candidate,
        factory_skill_catalog_candidate=skill_candidate,
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


def test_controlled_install_binds_factory_package_to_exact_artifact_digest(tmp_path: Path):
    package, profile, dashboard, northbound = _surfaces(tmp_path)
    candidate = _candidate(package)
    skill_candidate = _skill_candidate(tmp_path)
    plan = _build(package, candidate, skill_candidate, profile, dashboard, northbound)

    assert plan.ready_for_controlled_execution is True
    package_operation = next(
        operation
        for operation in plan.operations
        if operation.component is RuntimeComponent.FACTORY_PACKAGE
    )
    assert package_operation.source == str(package)
    assert package_operation.source_digest == candidate.artifact_digest
    assert package_operation.target == "HERMES_RUNTIME_ENV"


def test_controlled_install_blocks_factory_package_digest_drift(tmp_path: Path):
    package, profile, dashboard, northbound = _surfaces(tmp_path)
    candidate = _candidate(package)
    skill_candidate = _skill_candidate(tmp_path)
    package.write_bytes(b"changed after package identity was recorded")

    plan = _build(package, candidate, skill_candidate, profile, dashboard, northbound)

    assert plan.ready_for_controlled_execution is False
    assert plan.execution_state == "BLOCKED"
    assert any("Factory package digest drift" in blocker for blocker in plan.blockers)
