from pathlib import Path

WORKFLOW = Path(".github/workflows/factory-ci.yml")


def test_factory_ci_emits_exact_head_skill_catalog_candidate() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "factory-skill-catalog-candidate:" in source
    assert "build_skill_catalog_candidate" in source
    assert "skills/registry.yaml" in source
    assert "artifacts/factory-skill-catalog" in source
    assert "factory-skill-catalog-candidate-${{ env.FACTORY_CANDIDATE_SHA }}" in source
    assert "ref: ${{ env.FACTORY_CANDIDATE_SHA }}" in source
