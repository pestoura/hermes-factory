from pathlib import Path

import pytest

from hermes_factory.gates import ExactSHAState, evaluate_exact_sha
from hermes_factory.traceability import EvidenceConflict, SemanticRegistry


def test_registry_preserves_entity_and_edge_traceability(tmp_path: Path):
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.add_entity("REQ-1", "Requirement", {"title": "Status must be truthful"})
    registry.add_entity("UAT-1", "UATScenario", {"mode": "AUTOMATED"})
    registry.add_edge("REQ-1", "UAT-1", "PROVED_BY")
    assert registry.has_edge("REQ-1", "UAT-1", "PROVED_BY") is True


def test_evidence_is_immutable_by_evidence_id(tmp_path: Path):
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.record_evidence("EV-1", kind="CI", state="PASS", candidate="abc", payload={"run": 1})
    with pytest.raises(EvidenceConflict):
        registry.record_evidence("EV-1", kind="CI", state="PASS", candidate="def", payload={"run": 2})


def test_changed_candidate_can_stale_previous_evidence(tmp_path: Path):
    registry = SemanticRegistry(tmp_path / "factory.db")
    registry.record_evidence("EV-1", kind="CI", state="PASS", candidate="abc", payload={})
    assert registry.mark_evidence_stale_for_candidate("abc") == 1
    assert registry.get_evidence("EV-1")["state"] == "STALE"


def test_exact_sha_match_requires_all_required_identity_to_match():
    assert evaluate_exact_sha("abc", ["abc", "abc"]) is ExactSHAState.SHA_MATCH
    assert evaluate_exact_sha("abc", ["abc", "def"]) is ExactSHAState.SHA_MISMATCH


def test_exact_sha_refuses_missing_or_unknown_identity():
    assert evaluate_exact_sha("abc", []) is ExactSHAState.EVIDENCE_ABSENT
    assert evaluate_exact_sha("abc", [None]) is ExactSHAState.IDENTITY_UNKNOWN
    assert evaluate_exact_sha(None, ["abc"]) is ExactSHAState.IDENTITY_UNKNOWN


def test_stale_evidence_precedes_equality_claim():
    assert evaluate_exact_sha("abc", ["abc"], stale=True) is ExactSHAState.EVIDENCE_STALE
