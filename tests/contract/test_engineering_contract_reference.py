from pathlib import Path

import pytest

import hermes_factory.contracts as contracts


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "engineering.yml"
    path.write_text(text)
    return path


def test_jds_engineering_reference_loads_identity_without_reimplementing_jds(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
apiVersion: engineering.jarvas/v1
kind: ProjectEngineeringProfile
metadata:
  name: demo
spec:
  standard: JDS-1.0
  platformRef: 9ee1147ea85bbb5bbb733d252bab9ccbb113f5ef
  criticality: high
  capabilities:
    add: [security.secret-scan]
    remove: []
  overrides:
    future-control:
      mode: strict
""",
    )

    ref = contracts.EngineeringProfileReference.from_yaml(path)

    assert ref.api_version == "engineering.jarvas/v1"
    assert ref.kind == "ProjectEngineeringProfile"
    assert ref.standard == "JDS-1.0"
    assert ref.platform_ref == "9ee1147ea85bbb5bbb733d252bab9ccbb113f5ef"
    assert ref.criticality == "high"
    assert len(ref.digest) == 64


def test_jds_reference_digest_is_semantic_and_key_order_independent(tmp_path: Path) -> None:
    first = _write(
        tmp_path,
        """
apiVersion: engineering.jarvas/v1
kind: ProjectEngineeringProfile
spec:
  standard: JDS-1.0
  platformRef: abc
  criticality: low
""",
    )
    first_digest = contracts.EngineeringProfileReference.from_yaml(first).digest

    second = tmp_path / "engineering-2.yml"
    second.write_text(
        """
kind: ProjectEngineeringProfile
spec:
  criticality: low
  platformRef: abc
  standard: JDS-1.0
apiVersion: engineering.jarvas/v1
"""
    )

    assert contracts.EngineeringProfileReference.from_yaml(second).digest == first_digest


def test_jds_reference_fails_closed_on_missing_identity_but_accepts_future_jds_fields(
    tmp_path: Path,
) -> None:
    missing = _write(
        tmp_path,
        """
apiVersion: engineering.jarvas/v1
kind: ProjectEngineeringProfile
spec:
  standard: JDS-1.0
  criticality: low
""",
    )
    with pytest.raises(contracts.ContractValidationError, match="platformRef"):
        contracts.EngineeringProfileReference.from_yaml(missing)

    future = tmp_path / "future.yml"
    future.write_text(
        """
apiVersion: engineering.jarvas/v1
kind: ProjectEngineeringProfile
metadata:
  name: demo
  futureMetadata: accepted-by-jds
spec:
  standard: JDS-1.0
  platformRef: abc
  criticality: low
  futureJdsSection:
    arbitrary: true
"""
    )
    contracts.EngineeringProfileReference.from_yaml(future)


def test_jds_reference_rejects_wrong_document_kind(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
apiVersion: engineering.jarvas/v1
kind: SomethingElse
spec:
  standard: JDS-1.0
  platformRef: abc
  criticality: low
""",
    )
    with pytest.raises(contracts.ContractValidationError, match="kind"):
        contracts.EngineeringProfileReference.from_yaml(path)
