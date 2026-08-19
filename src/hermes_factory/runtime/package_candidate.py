from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_factory.governance.candidate_identity import digest_artifact


class PackageCandidateError(ValueError):
    pass


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_CONTENT_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "hermes.factory/package-candidate/v2"


@dataclass(frozen=True)
class FactoryPackageCandidate:
    candidate_sha: str
    wheel_path: Path
    filename: str
    artifact_digest: str
    content_sha256: str
    size_bytes: int


def build_package_candidate_manifest(
    *,
    wheel_path: Path,
    candidate_sha: str,
    output_path: Path,
) -> dict[str, object]:
    if not _SHA_RE.fullmatch(candidate_sha):
        raise PackageCandidateError("candidate_sha must be an exact 40-character Git SHA")

    wheel = Path(wheel_path)
    if wheel.suffix != ".whl":
        raise PackageCandidateError("Factory package candidate must be a wheel")
    if wheel.is_symlink() or not wheel.is_file():
        raise PackageCandidateError("Factory package candidate wheel must be a regular file")

    wheel_bytes = wheel.read_bytes()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema": _SCHEMA,
        "candidate_sha": candidate_sha.lower(),
        "filename": wheel.name,
        "artifact_digest": digest_artifact(wheel),
        "content_sha256": hashlib.sha256(wheel_bytes).hexdigest(),
        "size_bytes": len(wheel_bytes),
    }
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PackageCandidateError("Factory package manifest must be a regular file")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageCandidateError("Factory package manifest is unreadable or invalid JSON") from exc
    if not isinstance(document, dict):
        raise PackageCandidateError("Factory package manifest must contain a JSON object")
    return document


def load_package_candidate(
    *,
    manifest_path: Path,
    wheel_path: Path,
    expected_candidate_sha: str,
) -> FactoryPackageCandidate:
    if not _SHA_RE.fullmatch(expected_candidate_sha):
        raise PackageCandidateError("expected candidate SHA must be an exact 40-character Git SHA")

    wheel = Path(wheel_path)
    if wheel.suffix != ".whl":
        raise PackageCandidateError("Factory package candidate must be a wheel")
    if wheel.is_symlink() or not wheel.is_file():
        raise PackageCandidateError("Factory package candidate wheel must be a regular file")

    document = _load_manifest(Path(manifest_path))
    schema = document.get("schema")
    if schema != _SCHEMA:
        raise PackageCandidateError(f"unsupported Factory package manifest schema: {schema!r}")

    candidate_sha = document.get("candidate_sha")
    if not isinstance(candidate_sha, str) or not _SHA_RE.fullmatch(candidate_sha):
        raise PackageCandidateError("Factory package manifest candidate SHA is invalid")
    if candidate_sha.lower() != expected_candidate_sha.lower():
        raise PackageCandidateError(
            "Factory package candidate SHA does not match expected exact head"
        )

    filename = document.get("filename")
    if not isinstance(filename, str) or filename != wheel.name:
        raise PackageCandidateError("Factory package manifest filename does not match wheel")

    content_sha256 = document.get("content_sha256")
    if not isinstance(content_sha256, str) or not _CONTENT_SHA_RE.fullmatch(content_sha256):
        raise PackageCandidateError("Factory package manifest content SHA-256 is invalid")
    wheel_bytes = wheel.read_bytes()
    observed_content_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
    if observed_content_sha256 != content_sha256:
        raise PackageCandidateError(
            "Factory package content SHA-256 does not match downloaded wheel"
        )

    size_bytes = document.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise PackageCandidateError("Factory package manifest size_bytes is invalid")
    if len(wheel_bytes) != size_bytes:
        raise PackageCandidateError("Factory package manifest size does not match wheel")

    artifact_digest = document.get("artifact_digest")
    if not isinstance(artifact_digest, str):
        raise PackageCandidateError("Factory package manifest artifact_digest is invalid")
    observed_artifact_digest = digest_artifact(wheel)
    if observed_artifact_digest != artifact_digest:
        raise PackageCandidateError(
            "Factory package canonical artifact digest does not match downloaded wheel"
        )

    return FactoryPackageCandidate(
        candidate_sha=candidate_sha.lower(),
        wheel_path=wheel,
        filename=filename,
        artifact_digest=artifact_digest,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
    )
