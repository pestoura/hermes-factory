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


def _skill_candidate(tmp_path: Path, candidate_sha: str):
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
        candidate_sha=candidate_sha,
        output_root=tmp_path / "skill-candidate",
    )


def _inputs(tmp_path: Path, candidate_sha: str):
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"verified package candidate")
    manifest = tmp_path / "factory-package.json"
    build_package_candidate_manifest(
        wheel_path=wheel,
        candidate_sha=candidate_sha,
        output_path=manifest,
    )
    candidate = load_package_candidate(
        manifest_path=manifest,
        wheel_path=wheel,
        expected_candidate_sha=candidate_sha,
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
    return candidate, profile, dashboard, northbound


def _build(tmp_path: Path, expected_factory_candidate_sha: str, actual_candidate_sha: str):
    candidate, profile, dashboard, northbound = _inputs(tmp_path, actual_candidate_sha)
    skill_candidate = _skill_candidate(tmp_path, actual_candidate_sha)
    return ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="a" * 40,
        observed_hermes_sha="a" * 40,
        expected_factory_candidate_sha=expected_factory_candidate_sha,
        factory_package_candidate=candidate,
        factory_skill_catalog_candidate=skill_candidate,
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


def test_install_plan_binds_verified_package_candidate_and_factory_exact_head(tmp_path: Path):
    candidate_sha = "b" * 40
    plan = _build(tmp_path, candidate_sha, candidate_sha)

    assert plan.ready_for_controlled_execution is True
    assert plan.factory_candidate_sha == candidate_sha
    manifest = plan.to_manifest()
    assert manifest["factory_candidate_sha"] == candidate_sha
    package_operation = next(
        operation
        for operation in plan.operations
        if operation.component is RuntimeComponent.FACTORY_PACKAGE
    )
    assert package_operation.source_digest.startswith("sha256:")


def test_install_plan_blocks_verified_package_from_wrong_factory_head(tmp_path: Path):
    plan = _build(tmp_path, "c" * 40, "d" * 40)

    assert plan.ready_for_controlled_execution is False
    assert plan.execution_state == "BLOCKED"
    assert any("exact Factory candidate SHA" in blocker for blocker in plan.blockers)
