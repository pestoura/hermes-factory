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

_FACTORY_SHA = "a" * 40


def _skill_candidate(tmp_path: Path):
    source_root = tmp_path / "skills"
    skill = source_root / "core" / "example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: factory-example\ndescription: Example\n---\n# Example\n",
        encoding="utf-8",
    )
    registry = {
        "schema": "hermes.factory/skills/v1.2",
        "registry": {
            "core": ["factory-example"],
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
        source_root=source_root,
        registry_document=registry,
        candidate_sha=_FACTORY_SHA,
        output_root=tmp_path / "skill-candidate",
    )


def _build(tmp_path: Path):
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"verified package candidate")
    manifest = tmp_path / "factory-package.json"
    build_package_candidate_manifest(
        wheel_path=wheel,
        candidate_sha=_FACTORY_SHA,
        output_path=manifest,
    )
    package_candidate = load_package_candidate(
        manifest_path=manifest,
        wheel_path=wheel,
        expected_candidate_sha=_FACTORY_SHA,
    )
    skill_candidate = _skill_candidate(tmp_path)

    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n")
    dashboard = tmp_path / "dashboard-plugin" / "hermes-factory"
    (dashboard / "dashboard").mkdir(parents=True)
    (dashboard / "dashboard" / "manifest.json").write_text("{}\n")
    northbound = tmp_path / "factory-northbound.yaml"
    northbound.write_text("component: NORTHBOUND_CONTROL_INTEGRATION\n")

    plan = ControlledInstallPlanBuilder().build(
        accepted_hermes_sha="b" * 40,
        observed_hermes_sha="b" * 40,
        expected_factory_candidate_sha=_FACTORY_SHA,
        factory_package_candidate=package_candidate,
        factory_skill_catalog_candidate=skill_candidate,
        profile_artifacts={"factory-orchestrator": profile},
        expected_profile_digests={"factory-orchestrator": digest_artifact(profile)},
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-example": AdmissionEvidenceState.PASS},
        component_states={component: AdmissionEvidenceState.PASS for component in RuntimeComponent},
        cron_plan=NativeCronPlanBuilder().build({}),
        dashboard_plugin_source=dashboard,
        gateway_adapter_module="hermes_factory.adapters.hermes_gateway",
        northbound_binding_source=northbound,
    )
    return plan, skill_candidate


def test_install_plan_binds_exact_head_private_skill_catalog_candidate(tmp_path: Path) -> None:
    plan, candidate = _build(tmp_path)

    operation = next(
        item for item in plan.operations if item.component is RuntimeComponent.FACTORY_SKILLS
    )
    assert operation.action == "STAGE_FACTORY_SKILL_CATALOG"
    assert operation.source == str(candidate.candidate_root)
    assert operation.source_digest == candidate.artifact_digest
    assert operation.target == f"HERMES_HOME/factory/skill-catalog/{_FACTORY_SHA}"
    assert plan.ready_for_controlled_execution is True
