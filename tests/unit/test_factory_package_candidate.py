import hashlib
import json
from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact


def test_factory_package_candidate_manifest_binds_wheel_to_exact_head(tmp_path: Path):
    from hermes_factory.runtime.package_candidate import build_package_candidate_manifest

    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"exact wheel bytes")
    output = tmp_path / "factory-package.json"
    candidate_sha = "a" * 40

    manifest = build_package_candidate_manifest(
        wheel_path=wheel,
        candidate_sha=candidate_sha,
        output_path=output,
    )

    assert manifest["schema"] == "hermes.factory/package-candidate/v2"
    assert manifest["candidate_sha"] == candidate_sha
    assert manifest["filename"] == wheel.name
    assert manifest["artifact_digest"] == digest_artifact(wheel)
    assert manifest["content_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert "sha256" not in manifest
    assert manifest["size_bytes"] == wheel.stat().st_size
    assert json.loads(output.read_text(encoding="utf-8")) == manifest


def test_factory_package_candidate_rejects_non_exact_sha_and_non_wheel(tmp_path: Path):
    from hermes_factory.runtime.package_candidate import (
        PackageCandidateError,
        build_package_candidate_manifest,
    )

    not_wheel = tmp_path / "package.tar.gz"
    not_wheel.write_bytes(b"candidate")

    with pytest.raises(PackageCandidateError, match="40-character"):
        build_package_candidate_manifest(
            wheel_path=not_wheel,
            candidate_sha="abc",
            output_path=tmp_path / "invalid-sha.json",
        )

    with pytest.raises(PackageCandidateError, match="wheel"):
        build_package_candidate_manifest(
            wheel_path=not_wheel,
            candidate_sha="b" * 40,
            output_path=tmp_path / "invalid-wheel.json",
        )
