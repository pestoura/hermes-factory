from __future__ import annotations

from pathlib import Path

import pytest

from hermes_factory.runtime.skill_catalog_candidate import (
    SkillCatalogCandidateError,
    build_skill_catalog_candidate,
    load_skill_catalog_candidate,
)

_FACTORY_SHA = "a" * 40


def _registry_document() -> dict[str, object]:
    return {
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


def _source_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    source = root / "core" / "example"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: factory-example\n"
        "description: Example Factory Skill\n"
        "---\n"
        "# Example\n",
        encoding="utf-8",
    )
    return root


def test_build_and_load_exact_head_private_skill_catalog_candidate(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    built = build_skill_catalog_candidate(
        source_root=_source_root(tmp_path),
        registry_document=_registry_document(),
        candidate_sha=_FACTORY_SHA,
        output_root=output,
    )

    assert built.candidate_sha == _FACTORY_SHA
    assert built.catalog_path == output / "catalog"
    assert built.manifest_path == output / "factory-skill-catalog.json"
    assert set(built.skill_sources) == {"factory-example"}
    assert set(built.skill_digests) == {"factory-example"}
    assert built.registry_document == _registry_document()
    assert built.registry_digest.startswith("sha256:")
    assert built.artifact_digest.startswith("sha256:")

    loaded = load_skill_catalog_candidate(
        candidate_root=output,
        expected_candidate_sha=_FACTORY_SHA,
    )

    assert loaded.candidate_sha == built.candidate_sha
    assert loaded.catalog_digest == built.catalog_digest
    assert loaded.skill_digests == built.skill_digests
    assert loaded.registry_document == _registry_document()
    assert loaded.registry_digest == built.registry_digest
    assert loaded.artifact_digest == built.artifact_digest


def test_skill_catalog_loader_rejects_content_tamper(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    build_skill_catalog_candidate(
        source_root=_source_root(tmp_path),
        registry_document=_registry_document(),
        candidate_sha=_FACTORY_SHA,
        output_root=output,
    )
    (output / "catalog" / "factory-example" / "SKILL.md").write_text(
        "tampered after candidate build\n",
        encoding="utf-8",
    )

    with pytest.raises(SkillCatalogCandidateError, match="digest"):
        load_skill_catalog_candidate(
            candidate_root=output,
            expected_candidate_sha=_FACTORY_SHA,
        )


def test_skill_catalog_loader_rejects_wrong_exact_head(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    build_skill_catalog_candidate(
        source_root=_source_root(tmp_path),
        registry_document=_registry_document(),
        candidate_sha=_FACTORY_SHA,
        output_root=output,
    )

    with pytest.raises(SkillCatalogCandidateError, match="candidate SHA"):
        load_skill_catalog_candidate(
            candidate_root=output,
            expected_candidate_sha="b" * 40,
        )


def test_skill_catalog_loader_rejects_symlinked_skill_content(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    build_skill_catalog_candidate(
        source_root=_source_root(tmp_path),
        registry_document=_registry_document(),
        candidate_sha=_FACTORY_SHA,
        output_root=output,
    )
    skill = output / "catalog" / "factory-example"
    original = skill / "SKILL.md"
    outside = tmp_path / "outside.md"
    outside.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    original.unlink()
    original.symlink_to(outside)

    with pytest.raises(SkillCatalogCandidateError, match="symlink"):
        load_skill_catalog_candidate(
            candidate_root=output,
            expected_candidate_sha=_FACTORY_SHA,
        )


def test_skill_catalog_loader_rejects_registry_policy_digest_tamper(tmp_path: Path) -> None:
    import json

    output = tmp_path / "candidate"
    build_skill_catalog_candidate(
        source_root=_source_root(tmp_path),
        registry_document=_registry_document(),
        candidate_sha=_FACTORY_SHA,
        output_root=output,
    )
    manifest = output / "factory-skill-catalog.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["skill_registry"]["registry"]["consumers"]["factory-example-agent"] = {
        "required": ["factory-example"]
    }
    manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(SkillCatalogCandidateError, match="registry digest"):
        load_skill_catalog_candidate(
            candidate_root=output,
            expected_candidate_sha=_FACTORY_SHA,
        )
