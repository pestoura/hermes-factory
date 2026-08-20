from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.hermes_install_runtime import HermesJarvasInstallRuntime
from hermes_factory.runtime.install import InstallOperation
from hermes_factory.runtime.skill_catalog_candidate import build_skill_catalog_candidate

_FACTORY_SHA = "a" * 40


class NoCommandRunner:
    def run(self, argv: tuple[str, ...]):
        raise AssertionError(f"Skill catalog staging must not execute commands: {argv}")


def _candidate(tmp_path: Path):
    source_root = tmp_path / "skills"
    source = source_root / "core" / "example"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
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
        output_root=tmp_path / "candidate",
    )


def _operation(candidate) -> InstallOperation:
    return InstallOperation(
        component=RuntimeComponent.FACTORY_SKILLS,
        action="STAGE_FACTORY_SKILL_CATALOG",
        source=str(candidate.candidate_root),
        source_digest=candidate.artifact_digest,
        target=f"HERMES_HOME/factory/skill-catalog/{_FACTORY_SHA}",
    )


def test_stage_private_skill_catalog_and_rollback(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    runtime = HermesJarvasInstallRuntime(
        hermes_home=hermes_home,
        command_runner=NoCommandRunner(),
    )
    operation = _operation(candidate)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)

    target = hermes_home / "factory" / "skill-catalog" / _FACTORY_SHA
    assert target.is_dir()
    assert digest_artifact(target) == candidate.artifact_digest
    assert not (hermes_home / "skills" / "factory-example").exists()
    assert not (hermes_home / "profiles" / "factory-example").exists()

    runtime.rollback(operation, receipt)

    assert not target.exists()
    assert not (hermes_home / "factory").exists()


def test_stage_skill_catalog_rejects_target_sha_mismatch(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    runtime = HermesJarvasInstallRuntime(
        hermes_home=hermes_home,
        command_runner=NoCommandRunner(),
    )
    operation = InstallOperation(
        component=RuntimeComponent.FACTORY_SKILLS,
        action="STAGE_FACTORY_SKILL_CATALOG",
        source=str(candidate.candidate_root),
        source_digest=candidate.artifact_digest,
        target=f"HERMES_HOME/factory/skill-catalog/{'b' * 40}",
    )

    try:
        runtime.preflight((operation,))
    except RuntimeError as exc:
        assert "candidate SHA" in str(exc)
    else:
        raise AssertionError("candidate SHA mismatch must fail closed")


def test_stage_skill_catalog_rejects_source_digest_mismatch(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    runtime = HermesJarvasInstallRuntime(
        hermes_home=hermes_home,
        command_runner=NoCommandRunner(),
    )
    operation = InstallOperation(
        component=RuntimeComponent.FACTORY_SKILLS,
        action="STAGE_FACTORY_SKILL_CATALOG",
        source=str(candidate.candidate_root),
        source_digest="sha256:" + "0" * 64,
        target=f"HERMES_HOME/factory/skill-catalog/{_FACTORY_SHA}",
    )

    try:
        runtime.preflight((operation,))
    except RuntimeError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("Skill catalog source digest mismatch must fail closed")
