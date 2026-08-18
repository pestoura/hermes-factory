from dataclasses import replace

import pytest

from hermes_factory.domain import HandoffState
from hermes_factory.handoff.ledger import HandoffConflict, SemanticHandoffLedger
from hermes_factory.handoff.service import HandoffRecord
from hermes_factory.traceability.registry import SemanticRegistry


def _record() -> HandoffRecord:
    return HandoffRecord(
        handoff_id="H-9",
        project_id="jarvas-cli",
        work_package_id="WP-9",
        stage="CODE_REVIEW",
        producer_profile="factory-code-reviewer",
        stage_outcome="PASS",
        artifact_refs=("artifact:review",),
        evidence_refs=("evidence:review",),
        evidence_states=("PASS",),
        finding_state="NONE",
        next_stage_prerequisites=(True,),
        context_revision="ctx-9",
        candidate_identity="sha9",
        candidate_identity_required=True,
        independent_review_required=True,
        independent_review_state="PASS",
    )


def test_handoff_record_survives_registry_reopen_and_state_transition(tmp_path) -> None:
    path = tmp_path / "factory.db"
    ledger = SemanticHandoffLedger(SemanticRegistry(path))
    ledger.commit(_record(), HandoffState.HANDOFF_READY)
    ledger.set_state("H-9", HandoffState.HANDED_OFF)

    reopened = SemanticHandoffLedger(SemanticRegistry(path))
    stored = reopened.get("H-9")

    assert stored.record == _record()
    assert stored.state is HandoffState.HANDED_OFF


def test_handoff_payload_is_immutable_and_terminal_state_cannot_be_rewritten(tmp_path) -> None:
    ledger = SemanticHandoffLedger(SemanticRegistry(tmp_path / "factory.db"))
    ledger.commit(_record(), HandoffState.HANDOFF_READY)

    with pytest.raises(HandoffConflict, match="immutable"):
        ledger.commit(
            replace(_record(), producer_profile="factory-software-engineer"),
            HandoffState.HANDOFF_READY,
        )

    ledger.set_state("H-9", HandoffState.HANDED_OFF)
    with pytest.raises(HandoffConflict, match="transition"):
        ledger.set_state("H-9", HandoffState.HANDOFF_READY)
