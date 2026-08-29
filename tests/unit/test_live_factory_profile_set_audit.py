import json
from pathlib import Path

import pytest
import yaml

from hermes_factory.runtime.admission import AdmissionEvidenceState


def _audit_contract():
    try:
        from hermes_factory.governance.live_profile_set_audit import (
            audit_live_factory_profile_set,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("live Factory Profile set audit is not implemented") from exc
    return audit_live_factory_profile_set


def _write_catalog(root: Path, profile_ids: tuple[str, ...]) -> None:
    catalog = {"catalog": {"active_candidates": list(profile_ids)}}
    path = root / "agents" / "catalog-v1.2.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")


def test_live_factory_profile_set_passes_only_on_exact_set_equality(tmp_path: Path) -> None:
    audit = _audit_contract()
    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    expected = ("factory-a", "factory-b")
    _write_catalog(repo, expected)
    for profile_id in (*expected, "not-factory"):
        (hermes_home / "profiles" / profile_id).mkdir(parents=True)

    result = audit(repo_root=repo, hermes_home=hermes_home, candidate_sha="a" * 40)

    assert result.state is AdmissionEvidenceState.PASS
    assert result.expected_profile_ids == expected
    assert result.observed_profile_ids == expected
    assert result.missing_profile_ids == ()
    assert result.unexpected_profile_ids == ()
    assert result.to_manifest()["exact_set_match"] is True


def test_live_factory_profile_set_fails_on_unexpected_factory_profile(tmp_path: Path) -> None:
    audit = _audit_contract()
    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    expected = ("factory-a", "factory-b")
    _write_catalog(repo, expected)
    for profile_id in (*expected, "factory-extra"):
        (hermes_home / "profiles" / profile_id).mkdir(parents=True)

    result = audit(repo_root=repo, hermes_home=hermes_home, candidate_sha="b" * 40)

    assert result.state is AdmissionEvidenceState.FAIL
    assert result.missing_profile_ids == ()
    assert result.unexpected_profile_ids == ("factory-extra",)
    manifest = result.to_manifest()
    assert manifest["expected_count"] == 2
    assert manifest["observed_count"] == 3
    assert manifest["exact_set_match"] is False


def test_live_factory_profile_set_fails_on_missing_factory_profile(tmp_path: Path) -> None:
    audit = _audit_contract()
    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    expected = ("factory-a", "factory-b")
    _write_catalog(repo, expected)
    (hermes_home / "profiles" / "factory-a").mkdir(parents=True)

    result = audit(repo_root=repo, hermes_home=hermes_home, candidate_sha="c" * 40)

    assert result.state is AdmissionEvidenceState.FAIL
    assert result.missing_profile_ids == ("factory-b",)
    assert result.unexpected_profile_ids == ()


def test_live_factory_profile_set_fails_on_symlinked_factory_profile(tmp_path: Path) -> None:
    audit = _audit_contract()
    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    expected = ("factory-a",)
    _write_catalog(repo, expected)
    target = tmp_path / "profile-target"
    target.mkdir()
    profiles = hermes_home / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "factory-a").symlink_to(target, target_is_directory=True)

    result = audit(repo_root=repo, hermes_home=hermes_home, candidate_sha="d" * 40)

    assert result.state is AdmissionEvidenceState.FAIL
    assert result.invalid_profile_ids == ("factory-a",)
    assert result.to_manifest()["exact_set_match"] is False


def test_live_factory_profile_set_cli_evidence_is_write_once(tmp_path: Path) -> None:
    from hermes_factory.governance.live_profile_set_audit import main

    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    _write_catalog(repo, ("factory-a",))
    (hermes_home / "profiles" / "factory-a").mkdir(parents=True)
    output = tmp_path / "live-profile-set.json"
    argv = [
        "--repo-root", str(repo), "--hermes-home", str(hermes_home),
        "--candidate-sha", "e" * 40, "--output", str(output),
    ]

    assert main(argv) == 0
    assert json.loads(output.read_text())["state"] == "PASS"
    (hermes_home / "profiles" / "factory-extra").mkdir()
    with pytest.raises(ValueError, match="immutable"):
        main(argv)


def test_live_factory_profile_set_maps_directly_to_runtime_acceptance(tmp_path: Path) -> None:
    audit = _audit_contract()
    repo = tmp_path / "repo"
    hermes_home = tmp_path / "hermes"
    _write_catalog(repo, ("factory-a",))
    (hermes_home / "profiles" / "factory-a").mkdir(parents=True)
    (hermes_home / "profiles" / "factory-extra").mkdir()

    result = audit(repo_root=repo, hermes_home=hermes_home, candidate_sha="f" * 40)
    evidence = result.to_runtime_acceptance_evidence("file://phase-q/live-profile-set.json")

    assert evidence.scenario == "factory_profile_live_set_matches_canonical_catalog"
    assert evidence.candidate_sha == "f" * 40
    assert evidence.state is AdmissionEvidenceState.FAIL
    with pytest.raises(ValueError, match="provenance"):
        result.to_runtime_acceptance_evidence("")
