from pathlib import Path

import pytest
import yaml


def _contract():
    try:
        from hermes_factory.skills.artifacts import (
            SkillArtifactError,
            compile_skill_artifact,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("native Skill artifact projection is not implemented") from exc
    return SkillArtifactError, compile_skill_artifact


def test_legacy_skill_is_projected_as_native_canonical_skill_directory(tmp_path: Path):
    _, compile_skill_artifact = _contract()
    source = tmp_path / "reading-project-truth"
    source.mkdir()
    (source / "references").mkdir()
    (source / "references" / "guide.md").write_text("guide\n", encoding="utf-8")
    (source / "SKILL.md").write_text(
        "---\nname: reading-project-truth\ndescription: Truth\nversion: 0.1.0\n---\n\n# Truth\n",
        encoding="utf-8",
    )

    destination = tmp_path / "distribution" / "skills"
    compiled = compile_skill_artifact(
        source,
        canonical_id="factory-reading-project-truth",
        destination_root=destination,
    )

    assert compiled == destination / "factory-reading-project-truth"
    assert (compiled / "SKILL.md").is_file()
    assert (compiled / "references" / "guide.md").read_text(encoding="utf-8") == "guide\n"
    assert not list(destination.glob("*.skillref"))

    text = (compiled / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["name"] == "factory-reading-project-truth"
    assert "# Truth" in text


def test_already_canonical_skill_preserves_canonical_name(tmp_path: Path):
    _, compile_skill_artifact = _contract()
    source = tmp_path / "factory-classifying-findings"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: factory-classifying-findings\ndescription: Findings\n---\n\n# Findings\n",
        encoding="utf-8",
    )

    compiled = compile_skill_artifact(
        source,
        canonical_id="factory-classifying-findings",
        destination_root=tmp_path / "out",
    )

    frontmatter = yaml.safe_load(
        (compiled / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    )
    assert frontmatter["name"] == "factory-classifying-findings"


def test_skill_projection_rejects_symlinks_and_secret_like_files(tmp_path: Path):
    error_type, compile_skill_artifact = _contract()
    source = tmp_path / "skill"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: skill\ndescription: x\n---\n\n# Skill\n",
        encoding="utf-8",
    )
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    (source / "linked.txt").symlink_to(target)

    with pytest.raises(error_type, match="symlink"):
        compile_skill_artifact(
            source,
            canonical_id="factory-skill",
            destination_root=tmp_path / "out-a",
        )

    (source / "linked.txt").unlink()
    (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    with pytest.raises(error_type, match="forbidden"):
        compile_skill_artifact(
            source,
            canonical_id="factory-skill",
            destination_root=tmp_path / "out-b",
        )
