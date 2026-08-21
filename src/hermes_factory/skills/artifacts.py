from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml


class SkillArtifactError(ValueError):
    pass


_FORBIDDEN_NAMES = {
    ".env",
    ".env.example",
    "auth.json",
    "state.db",
    "state.db-shm",
    "state.db-wal",
    "hermes_state.db",
    "response_store.db",
    "response_store.db-shm",
    "response_store.db-wal",
    "gateway_state.json",
    "gateway.pid",
}
_SAFE_ID = re.compile(r"^factory-[a-z0-9][a-z0-9-]*$")


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        raise SkillArtifactError("SKILL.md requires YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SkillArtifactError("SKILL.md frontmatter is not terminated")
    raw = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise SkillArtifactError("SKILL.md frontmatter must be a mapping")
    return data, body


def _validate_source(source: Path) -> Path:
    if source.is_symlink():
        raise SkillArtifactError("Skill source cannot be a symlink")
    if not source.is_dir():
        raise SkillArtifactError("Skill source must be a directory")
    skill_file = source / "SKILL.md"
    if skill_file.is_symlink() or not skill_file.is_file():
        raise SkillArtifactError("Skill source requires a regular SKILL.md")
    for entry in source.rglob("*"):
        relative = entry.relative_to(source)
        if entry.is_symlink():
            raise SkillArtifactError(f"Skill source contains symlink: {relative.as_posix()}")
        if entry.name.lower() in _FORBIDDEN_NAMES:
            raise SkillArtifactError(
                f"Skill source contains forbidden file: {relative.as_posix()}"
            )
    return skill_file


def compile_skill_artifact(
    source: Path,
    *,
    canonical_id: str,
    destination_root: Path,
) -> Path:
    if not _SAFE_ID.fullmatch(canonical_id):
        raise SkillArtifactError("canonical Skill ID must use the factory-* namespace")

    source = Path(source)
    skill_file = _validate_source(source)
    frontmatter, body = _split_frontmatter(skill_file.read_text(encoding="utf-8"))
    frontmatter["name"] = canonical_id

    destination_root = Path(destination_root)
    destination = destination_root / canonical_id
    if destination.exists():
        raise SkillArtifactError(f"destination Skill already exists: {canonical_id}")
    destination.mkdir(parents=True, exist_ok=False)

    for entry in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        relative = entry.relative_to(source)
        target = destination / relative
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if entry == skill_file:
            continue
        if entry.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry, target)

    rendered = (
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).rstrip()
        + "\n---\n"
        + body
    )
    (destination / "SKILL.md").write_text(rendered, encoding="utf-8")
    return destination
