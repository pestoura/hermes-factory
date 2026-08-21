from pathlib import Path

import pytest

from hermes_factory.skills.system import (
    SkillAdmissionError,
    SkillEvalRecord,
    SkillRegistry,
    compile_native_skill,
)


def _registry_document():
    return {
        "schema": "hermes.factory/skills/v1.2",
        "registry": {
            "policy": {
                "canonical_id_prefix": "factory-",
                "promotion_requires": [
                    "baseline_red",
                    "skill_green",
                    "variation_eval",
                    "pressure_eval",
                    "independent_review",
                ],
            },
            "legacy_source_aliases": {
                "reading-project-truth": "factory-reading-project-truth",
                "implementing-minimal-green": "factory-implementing-minimal-green",
            },
            "core": ["factory-reading-project-truth"],
            "engineering_quality": ["factory-implementing-minimal-green"],
            "control_workforce": [],
            "product_architecture": [],
            "documentation": [],
            "security_assurance": [],
            "governance_operations": [],
            "proposed_v1_2_skills": {},
            "superseded_skill_concepts": {
                "verifying-exact-sha": {"replaced_by": "gate:factory-exact-sha"}
            },
            "consumers": {
                "factory-software-engineer": {
                    "required": ["factory-reading-project-truth"],
                    "task_optional": ["factory-implementing-minimal-green"],
                }
            },
        },
    }


def test_registry_resolves_legacy_aliases_and_rejects_unknown_or_noncanonical_entries():
    registry = SkillRegistry.from_document(_registry_document())

    assert registry.resolve("reading-project-truth") == "factory-reading-project-truth"
    assert registry.resolve("factory-reading-project-truth") == "factory-reading-project-truth"
    with pytest.raises(SkillAdmissionError, match="not registered"):
        registry.resolve("factory-not-real")

    broken = _registry_document()
    broken["registry"]["core"] = ["reading-project-truth"]
    with pytest.raises(SkillAdmissionError, match="canonical"):
        SkillRegistry.from_document(broken)


def test_effective_skills_are_authorized_union_and_all_must_be_admitted():
    registry = SkillRegistry.from_document(_registry_document())

    assert registry.effective_skills(
        "factory-software-engineer",
        task_approved=("implementing-minimal-green",),
        admitted=frozenset(
            {"factory-reading-project-truth", "factory-implementing-minimal-green"}
        ),
    ) == ("factory-implementing-minimal-green", "factory-reading-project-truth")

    with pytest.raises(SkillAdmissionError, match="not admitted"):
        registry.effective_skills(
            "factory-software-engineer",
            task_approved=("factory-implementing-minimal-green",),
            admitted=frozenset({"factory-reading-project-truth"}),
        )
    with pytest.raises(SkillAdmissionError, match="not authorized"):
        registry.effective_skills(
            "factory-software-engineer",
            task_approved=("factory-not-real",),
            admitted=frozenset({"factory-reading-project-truth"}),
        )


def test_skill_promotion_requires_all_five_evaluation_gates():
    incomplete = SkillEvalRecord(
        baseline_red=True,
        skill_green=True,
        variation_eval=True,
        pressure_eval=False,
        independent_review=True,
    )
    assert incomplete.promotable is False
    with pytest.raises(SkillAdmissionError, match="cannot be ACTIVE"):
        incomplete.require_active("factory-reading-project-truth")

    complete = SkillEvalRecord(
        baseline_red=True,
        skill_green=True,
        variation_eval=True,
        pressure_eval=True,
        independent_review=True,
    )
    admission = complete.require_active("factory-reading-project-truth")
    assert complete.promotable is True
    assert admission.skill_id == "factory-reading-project-truth"
    assert admission.version == "1.0.0"
    assert admission.lifecycle == "ACTIVE"


def test_compiler_rewrites_native_skill_identity_and_adds_canonical_provenance(tmp_path: Path):
    registry = SkillRegistry.from_document(_registry_document())
    source = tmp_path / "source" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\n"
        "name: implementing-minimal-green\n"
        "description: Minimal GREEN\n"
        "version: 0.1.0\n"
        "metadata:\n"
        "  factory:\n"
        "    lifecycle: proposed\n"
        "    test_status: not_run\n"
        "---\n\n"
        "# Minimal GREEN\n\nKeep the causal RED honest.\n"
    )

    output = compile_native_skill(
        source,
        source_id="implementing-minimal-green",
        registry=registry,
        destination=tmp_path / "compiled",
        origin_repo="pestoura/hermes-factory",
        origin_ref="abc123",
    )

    assert output == tmp_path / "compiled" / "factory-implementing-minimal-green" / "SKILL.md"
    text = output.read_text()
    assert "name: factory-implementing-minimal-green" in text
    assert "managed_by: hermes-factory" in text
    assert "origin_repo: pestoura/hermes-factory" in text
    assert "origin_ref: abc123" in text
    assert "Keep the causal RED honest." in text


def _write_skill(root: Path, folder: str, declared_name: str) -> None:
    path = root / folder / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"name: {declared_name}\n"
        "description: test\n"
        "version: 0.1.0\n"
        "---\n\n# Skill\n"
    )


def test_source_reconciliation_requires_exactly_one_source_per_registered_skill(tmp_path: Path):
    registry = SkillRegistry.from_document(_registry_document())
    _write_skill(tmp_path, "core/reading-project-truth", "reading-project-truth")
    _write_skill(
        tmp_path,
        "engineering/implementing-minimal-green",
        "implementing-minimal-green",
    )
    _write_skill(
        tmp_path,
        "governance/verifying-exact-sha",
        "verifying-exact-sha",
    )

    result = registry.reconcile_sources(tmp_path)

    assert result.sources == {
        "factory-reading-project-truth": (
            tmp_path / "core/reading-project-truth" / "SKILL.md"
        ),
        "factory-implementing-minimal-green": (
            tmp_path / "engineering/implementing-minimal-green" / "SKILL.md"
        ),
    }
    assert result.superseded_sources == (
        tmp_path / "governance/verifying-exact-sha" / "SKILL.md",
    )


def test_source_reconciliation_rejects_orphans_duplicates_and_missing_sources(tmp_path: Path):
    registry = SkillRegistry.from_document(_registry_document())
    _write_skill(tmp_path, "a/reading-project-truth", "reading-project-truth")
    _write_skill(
        tmp_path,
        "b/factory-reading-project-truth",
        "factory-reading-project-truth",
    )
    _write_skill(tmp_path, "c/not-real", "not-real")

    with pytest.raises(SkillAdmissionError, match="orphan|duplicate|missing"):
        registry.reconcile_sources(tmp_path)
