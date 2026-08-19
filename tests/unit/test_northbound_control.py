import pytest

from hermes_factory.traceability.registry import SemanticRegistry


def test_northbound_reads_are_external_candidate_bound_and_read_only(tmp_path) -> None:
    from hermes_factory.control import (
        NorthboundAccessDenied,
        NorthboundCaller,
        NorthboundControl,
        NorthboundOrigin,
    )

    registry = SemanticRegistry(tmp_path / "registry.db")
    registry.repository("Project").put(
        "project:factory",
        "rev-1",
        {"name": "Hermes Factory"},
    )
    registry.repository("AcceptanceDecision").put(
        "acceptance:sha-1",
        "sha-1",
        {
            "acceptance_class": "REPOSITORY",
            "candidate_sha": "sha-1",
            "state": "ACCEPTED",
        },
    )
    registry.repository("AcceptanceDecision").put(
        "acceptance:sha-2",
        "sha-2",
        {
            "acceptance_class": "REPOSITORY",
            "candidate_sha": "sha-2",
            "state": "ACCEPTED",
        },
    )
    registry.record_evidence(
        "evidence:sha-1",
        kind="CI",
        state="PASS",
        candidate="sha-1",
        payload={"check": "pytest"},
    )
    registry.record_evidence(
        "evidence:sha-2",
        kind="CI",
        state="PASS",
        candidate="sha-2",
        payload={"check": "pytest"},
    )

    control = NorthboundControl(registry)
    external = NorthboundCaller(
        principal="mcp:authorized-client",
        origin=NorthboundOrigin.EXTERNAL,
    )
    before_events = registry.list_events()

    status = control.status(candidate_sha="sha-1", caller=external)
    evidence = control.evidence(candidate_sha="sha-1", caller=external)
    acceptance = control.acceptance(candidate_sha="sha-1", caller=external)

    for operation, response in (
        ("STATUS", status),
        ("EVIDENCE", evidence),
        ("ACCEPTANCE", acceptance),
    ):
        assert response["schema_version"] == "1.0"
        assert response["operation"] == operation
        assert response["candidate_sha"] == "sha-1"
        assert isinstance(response["data"], dict)

    assert status["data"]["projects"][0]["entity_id"] == "project:factory"
    assert status["data"]["evidence_states"] == {"PASS": 1}
    assert [row["evidence_id"] for row in evidence["data"]["records"]] == [
        "evidence:sha-1"
    ]
    assert [row["entity_id"] for row in acceptance["data"]["records"]] == [
        "acceptance:sha-1"
    ]
    assert registry.list_events() == before_events

    internal = NorthboundCaller(
        principal="profile:factory-orchestrator",
        origin=NorthboundOrigin.INTERNAL_PROFILE,
    )
    with pytest.raises(NorthboundAccessDenied, match="internal profiles"):
        control.status(candidate_sha="sha-1", caller=internal)

    with pytest.raises(ValueError, match="candidate_sha"):
        control.status(candidate_sha=" ", caller=external)
    with pytest.raises(ValueError, match="principal"):
        control.status(
            candidate_sha="sha-1",
            caller=NorthboundCaller(principal=" ", origin=NorthboundOrigin.EXTERNAL),
        )
