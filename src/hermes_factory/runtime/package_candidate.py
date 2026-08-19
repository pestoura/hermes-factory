from __future__ import annotations

import json
import re
from pathlib import Path

from hermes_factory.governance.candidate_identity import digest_artifact


class PackageCandidateError(ValueError):
    pass


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


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

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema": "hermes.factory/package-candidate/v1",
        "candidate_sha": candidate_sha.lower(),
        "filename": wheel.name,
        "sha256": digest_artifact(wheel),
        "size_bytes": wheel.stat().st_size,
    }
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
