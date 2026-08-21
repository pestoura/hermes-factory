from pathlib import Path

from hermes_factory.gates import ExactSHAEvidenceGate, ExactSHAState
from hermes_factory.traceability import SemanticRegistry


def _registry(tmp_path: Path) -> SemanticRegistry:
    return SemanticRegistry(tmp_path / "factory.db")


def test_exact_sha_gate_derives_match_from_persisted_evidence(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.record_evidence(
        "EV-CI",
        kind="CI",
        state="PASS",
        candidate="candidate-a",
        payload={"run": 1},
    )
    registry.record_evidence(
        "EV-REVIEW",
        kind="REVIEW",
        state="PASS",
        candidate="candidate-a",
        payload={"review": 1},
    )

    gate = ExactSHAEvidenceGate(registry)

    assert gate.evaluate("candidate-a", ("EV-CI", "EV-REVIEW")) is ExactSHAState.SHA_MATCH


def test_exact_sha_gate_refuses_missing_mismatched_and_unknown_identity(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.record_evidence(
        "EV-CI",
        kind="CI",
        state="PASS",
        candidate="candidate-a",
        payload={},
    )
    registry.record_evidence(
        "EV-UNKNOWN",
        kind="CI",
        state="PASS",
        candidate=None,
        payload={},
    )
    gate = ExactSHAEvidenceGate(registry)

    assert gate.evaluate("candidate-a", ("EV-MISSING",)) is ExactSHAState.EVIDENCE_ABSENT
    assert gate.evaluate("candidate-b", ("EV-CI",)) is ExactSHAState.SHA_MISMATCH
    assert gate.evaluate("candidate-a", ("EV-UNKNOWN",)) is ExactSHAState.IDENTITY_UNKNOWN


def test_candidate_transition_stales_old_evidence_before_new_candidate_use(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.record_evidence(
        "EV-OLD-CI",
        kind="CI",
        state="PASS",
        candidate="candidate-a",
        payload={},
    )
    registry.record_evidence(
        "EV-OLD-REVIEW",
        kind="REVIEW",
        state="PASS",
        candidate="candidate-a",
        payload={},
    )
    registry.record_evidence(
        "EV-NEW-CI",
        kind="CI",
        state="PASS",
        candidate="candidate-b",
        payload={},
    )
    gate = ExactSHAEvidenceGate(registry)

    changed = gate.transition_candidate(
        previous_candidate="candidate-a",
        new_candidate="candidate-b",
    )

    assert changed == 2
    assert registry.get_evidence("EV-OLD-CI")["state"] == "STALE"
    assert registry.get_evidence("EV-OLD-REVIEW")["state"] == "STALE"
    assert registry.get_evidence("EV-NEW-CI")["state"] == "PASS"
    assert gate.evaluate("candidate-b", ("EV-OLD-CI",)) is ExactSHAState.EVIDENCE_STALE
    assert gate.evaluate("candidate-b", ("EV-NEW-CI",)) is ExactSHAState.SHA_MATCH


def test_candidate_transition_is_idempotent_and_does_not_stale_same_candidate(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.record_evidence(
        "EV-CI",
        kind="CI",
        state="PASS",
        candidate="candidate-a",
        payload={},
    )
    gate = ExactSHAEvidenceGate(registry)

    assert gate.transition_candidate(
        previous_candidate="candidate-a",
        new_candidate="candidate-a",
    ) == 0
    assert registry.get_evidence("EV-CI")["state"] == "PASS"

    assert gate.transition_candidate(
        previous_candidate="candidate-a",
        new_candidate="candidate-b",
    ) == 1
    assert gate.transition_candidate(
        previous_candidate="candidate-a",
        new_candidate="candidate-b",
    ) == 0
