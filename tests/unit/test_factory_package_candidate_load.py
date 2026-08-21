import json
from pathlib import Path

import pytest

from hermes_factory.runtime.package_candidate import build_package_candidate_manifest


def _candidate(tmp_path: Path):
    wheel = tmp_path / "hermes_factory-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"verified exact-head wheel")
    manifest = tmp_path / "factory-package.json"
    candidate_sha = "a" * 40
    build_package_candidate_manifest(
        wheel_path=wheel,
        candidate_sha=candidate_sha,
        output_path=manifest,
    )
    return wheel, manifest, candidate_sha


def test_load_package_candidate_verifies_manifest_and_wheel_identity(tmp_path: Path):
    from hermes_factory.runtime.package_candidate import load_package_candidate

    wheel, manifest, candidate_sha = _candidate(tmp_path)
    candidate = load_package_candidate(
        manifest_path=manifest,
        wheel_path=wheel,
        expected_candidate_sha=candidate_sha,
    )

    assert candidate.candidate_sha == candidate_sha
    assert candidate.wheel_path == wheel
    assert candidate.filename == wheel.name
    assert candidate.size_bytes == wheel.stat().st_size
    assert candidate.artifact_digest.startswith("sha256:")
    assert len(candidate.content_sha256) == 64


def test_load_package_candidate_rejects_wheel_tamper(tmp_path: Path):
    from hermes_factory.runtime.package_candidate import (
        PackageCandidateError,
        load_package_candidate,
    )

    wheel, manifest, candidate_sha = _candidate(tmp_path)
    wheel.write_bytes(b"tampered after artifact download")

    with pytest.raises(PackageCandidateError, match="content SHA-256"):
        load_package_candidate(
            manifest_path=manifest,
            wheel_path=wheel,
            expected_candidate_sha=candidate_sha,
        )


def test_load_package_candidate_rejects_wrong_head_filename_and_schema(tmp_path: Path):
    from hermes_factory.runtime.package_candidate import (
        PackageCandidateError,
        load_package_candidate,
    )

    wheel, manifest, candidate_sha = _candidate(tmp_path)

    with pytest.raises(PackageCandidateError, match="candidate SHA"):
        load_package_candidate(
            manifest_path=manifest,
            wheel_path=wheel,
            expected_candidate_sha="b" * 40,
        )

    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["filename"] = "other.whl"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PackageCandidateError, match="filename"):
        load_package_candidate(
            manifest_path=manifest,
            wheel_path=wheel,
            expected_candidate_sha=candidate_sha,
        )

    build_package_candidate_manifest(
        wheel_path=wheel,
        candidate_sha=candidate_sha,
        output_path=manifest,
    )
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["schema"] = "hermes.factory/package-candidate/v1"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PackageCandidateError, match="schema"):
        load_package_candidate(
            manifest_path=manifest,
            wheel_path=wheel,
            expected_candidate_sha=candidate_sha,
        )
