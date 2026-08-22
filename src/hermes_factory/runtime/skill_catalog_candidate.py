from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_factory.governance.candidate_identity import (
    CandidateIdentityError,
    digest_artifact,
)
from hermes_factory.skills.artifacts import SkillArtifactError, compile_skill_artifact
from hermes_factory.skills.system import SkillAdmissionError, SkillRegistry


class SkillCatalogCandidateError(ValueError):
    pass


_SCHEMA = "hermes.factory/skill-catalog-candidate/v1"
_MANIFEST = "factory-skill-catalog.json"
_CATALOG_DIR = "catalog"
_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_SKILL_ID = re.compile(r"^factory-[a-z0-9][a-z0-9-]*$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class FactorySkillCatalogCandidate:
    candidate_root: Path
    catalog_path: Path
    manifest_path: Path
    candidate_sha: str
    artifact_digest: str
    catalog_digest: str
    skill_digests: dict[str, str]
    registry_document: dict[str, Any]
    registry_digest: str

    @property
    def skill_sources(self) -> dict[str, Path]:
        return {
            skill_id: self.catalog_path / skill_id
            for skill_id in sorted(self.skill_digests)
        }


def _require_sha(value: str, label: str) -> str:
    if not isinstance(value, str) or not _GIT_SHA.fullmatch(value):
        raise SkillCatalogCandidateError(f"{label} must be an exact 40-character Git SHA")
    return value.lower()


def _require_regular_directory(path: Path, label: str) -> Path:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_dir():
        raise SkillCatalogCandidateError(f"{label} must be a regular directory")
    return candidate


def _digest(path: Path) -> str:
    try:
        return digest_artifact(path)
    except CandidateIdentityError as exc:
        raise SkillCatalogCandidateError(str(exc)) from exc


def _digest_json(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _manifest_payload(
    *,
    candidate_sha: str,
    catalog_digest: str,
    skill_digests: dict[str, str],
    registry_document: dict[str, Any],
    registry_digest: str,
) -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "candidate_sha": candidate_sha,
        "catalog_dir": _CATALOG_DIR,
        "catalog_digest": catalog_digest,
        "skill_count": len(skill_digests),
        "skills": {skill_id: skill_digests[skill_id] for skill_id in sorted(skill_digests)},
        "skill_registry": registry_document,
        "registry_digest": registry_digest,
    }


def build_skill_catalog_candidate(
    *,
    source_root: Path,
    registry_document: dict[str, Any],
    candidate_sha: str,
    output_root: Path,
) -> FactorySkillCatalogCandidate:
    exact_sha = _require_sha(candidate_sha, "candidate SHA")
    source_root = _require_regular_directory(Path(source_root), "Skill source root")
    output_root = Path(output_root)
    if output_root.exists() or output_root.is_symlink():
        raise SkillCatalogCandidateError("Skill catalog candidate output already exists")

    try:
        registry = SkillRegistry.from_document(registry_document)
        reconciled = registry.reconcile_sources(source_root)
    except SkillAdmissionError as exc:
        raise SkillCatalogCandidateError(str(exc)) from exc

    output_root.mkdir(parents=True, exist_ok=False)
    catalog_path = output_root / _CATALOG_DIR
    catalog_path.mkdir()
    skill_digests: dict[str, str] = {}
    try:
        for skill_id in sorted(reconciled.sources):
            if not _SKILL_ID.fullmatch(skill_id):
                raise SkillCatalogCandidateError(f"invalid canonical Skill ID: {skill_id}")
            source_file = reconciled.sources[skill_id]
            projected = compile_skill_artifact(
                source_file.parent,
                canonical_id=skill_id,
                destination_root=catalog_path,
            )
            skill_digests[skill_id] = _digest(projected)
    except (SkillArtifactError, CandidateIdentityError) as exc:
        raise SkillCatalogCandidateError(str(exc)) from exc

    catalog_digest = _digest(catalog_path)
    registry_digest = _digest_json(registry_document)
    manifest_path = output_root / _MANIFEST
    manifest_path.write_text(
        json.dumps(
            _manifest_payload(
                candidate_sha=exact_sha,
                catalog_digest=catalog_digest,
                skill_digests=skill_digests,
                registry_document=registry_document,
                registry_digest=registry_digest,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_digest = _digest(output_root)
    return FactorySkillCatalogCandidate(
        candidate_root=output_root,
        catalog_path=catalog_path,
        manifest_path=manifest_path,
        candidate_sha=exact_sha,
        artifact_digest=artifact_digest,
        catalog_digest=catalog_digest,
        skill_digests=skill_digests,
        registry_document=registry_document,
        registry_digest=registry_digest,
    )


def _load_manifest(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise SkillCatalogCandidateError("Skill catalog candidate manifest must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillCatalogCandidateError("Skill catalog candidate manifest is invalid") from exc
    if not isinstance(payload, dict):
        raise SkillCatalogCandidateError("Skill catalog candidate manifest must be an object")
    return payload


def _parse_skill_digests(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise SkillCatalogCandidateError("Skill catalog candidate skills must be a mapping")
    parsed: dict[str, str] = {}
    for raw_id, raw_digest in payload.items():
        if not isinstance(raw_id, str) or not _SKILL_ID.fullmatch(raw_id):
            raise SkillCatalogCandidateError("Skill catalog candidate contains invalid Skill ID")
        if not isinstance(raw_digest, str) or not _DIGEST.fullmatch(raw_digest):
            raise SkillCatalogCandidateError(f"Skill {raw_id} has invalid digest")
        parsed[raw_id] = raw_digest
    return parsed


def load_skill_catalog_candidate(
    *,
    candidate_root: Path,
    expected_candidate_sha: str,
) -> FactorySkillCatalogCandidate:
    expected_sha = _require_sha(expected_candidate_sha, "expected candidate SHA")
    candidate_root = _require_regular_directory(
        Path(candidate_root), "Skill catalog candidate root"
    )
    top_level = {entry.name for entry in candidate_root.iterdir()}
    if top_level != {_CATALOG_DIR, _MANIFEST}:
        raise SkillCatalogCandidateError("Skill catalog candidate contains unexpected entries")

    manifest_path = candidate_root / _MANIFEST
    payload = _load_manifest(manifest_path)
    if payload.get("schema") != _SCHEMA:
        raise SkillCatalogCandidateError("unsupported Skill catalog candidate schema")
    observed_sha = _require_sha(str(payload.get("candidate_sha", "")), "candidate SHA")
    if observed_sha != expected_sha:
        raise SkillCatalogCandidateError(
            f"candidate SHA mismatch: expected {expected_sha}, observed {observed_sha}"
        )
    if payload.get("catalog_dir") != _CATALOG_DIR:
        raise SkillCatalogCandidateError("Skill catalog candidate catalog_dir is invalid")

    skill_digests = _parse_skill_digests(payload.get("skills"))
    if payload.get("skill_count") != len(skill_digests):
        raise SkillCatalogCandidateError("Skill catalog candidate skill_count mismatch")

    registry_document = payload.get("skill_registry")
    if not isinstance(registry_document, dict):
        raise SkillCatalogCandidateError("Skill catalog candidate skill registry is invalid")
    try:
        SkillRegistry.from_document(registry_document)
    except SkillAdmissionError as exc:
        raise SkillCatalogCandidateError(str(exc)) from exc
    raw_registry_digest = payload.get("registry_digest")
    if not isinstance(raw_registry_digest, str) or not _DIGEST.fullmatch(raw_registry_digest):
        raise SkillCatalogCandidateError("Skill catalog candidate registry digest is invalid")
    observed_registry_digest = _digest_json(registry_document)
    if observed_registry_digest != raw_registry_digest:
        raise SkillCatalogCandidateError(
            "Skill catalog registry digest mismatch: "
            f"expected {raw_registry_digest}, observed {observed_registry_digest}"
        )

    catalog_path = _require_regular_directory(
        candidate_root / _CATALOG_DIR, "Skill catalog"
    )
    actual_entries = {entry.name for entry in catalog_path.iterdir()}
    if actual_entries != set(skill_digests):
        raise SkillCatalogCandidateError("Skill catalog candidate Skill set mismatch")

    for skill_id, expected_digest in skill_digests.items():
        source = _require_regular_directory(catalog_path / skill_id, f"Skill {skill_id}")
        observed_digest = _digest(source)
        if observed_digest != expected_digest:
            raise SkillCatalogCandidateError(
                f"Skill {skill_id} digest mismatch: "
                f"expected {expected_digest}, observed {observed_digest}"
            )

    raw_catalog_digest = payload.get("catalog_digest")
    if not isinstance(raw_catalog_digest, str) or not _DIGEST.fullmatch(raw_catalog_digest):
        raise SkillCatalogCandidateError("Skill catalog candidate catalog digest is invalid")
    observed_catalog_digest = _digest(catalog_path)
    if observed_catalog_digest != raw_catalog_digest:
        raise SkillCatalogCandidateError(
            "Skill catalog digest mismatch: "
            f"expected {raw_catalog_digest}, observed {observed_catalog_digest}"
        )

    return FactorySkillCatalogCandidate(
        candidate_root=candidate_root,
        catalog_path=catalog_path,
        manifest_path=manifest_path,
        candidate_sha=observed_sha,
        artifact_digest=_digest(candidate_root),
        catalog_digest=observed_catalog_digest,
        skill_digests=skill_digests,
        registry_document=registry_document,
        registry_digest=observed_registry_digest,
    )
