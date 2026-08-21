from pathlib import Path

from hermes_factory.traceability import SemanticRegistry


def test_evidence_record_and_stale_transition_are_provenance_audited(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.record_evidence(
        "EV-1",
        kind="CI",
        state="PASS",
        candidate="abc",
        payload={"run": 42},
    )

    assert registry.mark_evidence_stale_for_candidate("abc") == 1
    assert registry.mark_evidence_stale_for_candidate("abc") == 0
    assert registry.get_evidence("EV-1")["state"] == "STALE"

    events = registry.list_events(kind="EVIDENCE_RECORDED")
    assert len(events) == 1
    assert events[0]["payload"] == {
        "candidate": "abc",
        "evidence_id": "EV-1",
        "kind": "CI",
        "state": "PASS",
    }

    transitions = registry.list_events(kind="EVIDENCE_STATE_CHANGED")
    assert len(transitions) == 1
    assert transitions[0]["payload"] == {
        "candidate": "abc",
        "evidence_id": "EV-1",
        "from_state": "PASS",
        "to_state": "STALE",
    }


def test_staling_one_candidate_does_not_touch_other_evidence_or_emit_false_events(
    tmp_path: Path,
) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.record_evidence(
        "EV-A",
        kind="CI",
        state="PASS",
        candidate="abc",
        payload={},
    )
    registry.record_evidence(
        "EV-B",
        kind="CI",
        state="PASS",
        candidate="def",
        payload={},
    )

    assert registry.mark_evidence_stale_for_candidate("abc") == 1
    assert registry.get_evidence("EV-A")["state"] == "STALE"
    assert registry.get_evidence("EV-B")["state"] == "PASS"

    transitions = registry.list_events(kind="EVIDENCE_STATE_CHANGED")
    assert [event["payload"]["evidence_id"] for event in transitions] == ["EV-A"]
