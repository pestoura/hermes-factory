import os

import pytest


def _identity_contract():
    try:
        from hermes_factory.governance.candidate_identity import (
            CandidateIdentityError,
            digest_artifact,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("deterministic candidate identity is not implemented") from exc
    return CandidateIdentityError, digest_artifact


def test_directory_digest_is_stable_across_creation_order_and_mtime(tmp_path) -> None:
    _, digest_artifact = _identity_contract()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    (first / "b.txt").write_text("beta\n", encoding="utf-8")
    (first / "a.txt").write_text("alpha\n", encoding="utf-8")
    (second / "a.txt").write_text("alpha\n", encoding="utf-8")
    (second / "b.txt").write_text("beta\n", encoding="utf-8")
    os.utime(second / "a.txt", (1, 1))

    assert digest_artifact(first) == digest_artifact(second)
    assert digest_artifact(first).startswith("sha256:")
    assert len(digest_artifact(first)) == len("sha256:") + 64


def test_file_content_or_relative_path_change_changes_digest(tmp_path) -> None:
    _, digest_artifact = _identity_contract()
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for path in (first, second, third):
        path.mkdir()

    (first / "skill.md").write_text("same", encoding="utf-8")
    (second / "skill.md").write_text("changed", encoding="utf-8")
    (third / "renamed.md").write_text("same", encoding="utf-8")

    assert digest_artifact(first) != digest_artifact(second)
    assert digest_artifact(first) != digest_artifact(third)


def test_single_file_digest_is_deterministic(tmp_path) -> None:
    _, digest_artifact = _identity_contract()
    artifact = tmp_path / "SKILL.md"
    artifact.write_text("# Skill\n", encoding="utf-8")

    first = digest_artifact(artifact)
    os.utime(artifact, (2, 2))
    second = digest_artifact(artifact)

    assert first == second


def test_symlink_candidate_is_rejected_fail_closed(tmp_path) -> None:
    candidate_error, digest_artifact = _identity_contract()
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    link = tmp_path / "candidate-link"
    link.symlink_to(source)

    with pytest.raises(candidate_error, match="symlink"):
        digest_artifact(link)
