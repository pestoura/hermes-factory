from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hermes_factory.domain import HandoffState
from hermes_factory.handoff.service import HandoffRecord
from hermes_factory.traceability.registry import SemanticRegistry


class HandoffConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredHandoff:
    record: HandoffRecord
    state: HandoffState


class SemanticHandoffLedger:
    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def commit(self, record: HandoffRecord, state: HandoffState) -> None:
        record.validate()
        payload = _record_payload(record)
        self._registry.record_handoff(record.handoff_id, state=state.value, payload=payload)
        stored = self._registry.get_handoff(record.handoff_id)
        if stored["payload"] != payload:
            raise HandoffConflict(f"handoff {record.handoff_id} payload is immutable")
        if stored["state"] != state.value:
            raise HandoffConflict(
                f"handoff {record.handoff_id} already has state {stored['state']}"
            )

    def set_state(self, handoff_id: str, state: HandoffState) -> None:
        stored = self._registry.get_handoff(handoff_id)
        current = HandoffState(stored["state"])
        if current is state:
            return
        if current is HandoffState.HANDOFF_READY and state is HandoffState.HANDED_OFF:
            if self._registry.transition_handoff(
                handoff_id,
                expected_state=HandoffState.HANDOFF_READY.value,
                new_state=HandoffState.HANDED_OFF.value,
            ):
                return
        raise HandoffConflict(
            f"invalid handoff state transition {current.value} -> {state.value}"
        )

    def get(self, handoff_id: str) -> StoredHandoff:
        stored = self._registry.get_handoff(handoff_id)
        return StoredHandoff(
            record=_record_from_payload(stored["payload"]),
            state=HandoffState(stored["state"]),
        )


def _record_payload(record: HandoffRecord) -> dict[str, Any]:
    return {
        "handoff_id": record.handoff_id,
        "project_id": record.project_id,
        "work_package_id": record.work_package_id,
        "stage": record.stage,
        "producer_profile": record.producer_profile,
        "stage_outcome": record.stage_outcome,
        "artifact_refs": list(record.artifact_refs),
        "evidence_refs": list(record.evidence_refs),
        "evidence_states": list(record.evidence_states),
        "finding_state": record.finding_state,
        "next_stage_prerequisites": list(record.next_stage_prerequisites),
        "context_revision": record.context_revision,
        "candidate_identity": record.candidate_identity,
        "candidate_identity_required": record.candidate_identity_required,
        "independent_review_required": record.independent_review_required,
        "independent_review_state": record.independent_review_state,
    }


def _record_from_payload(payload: dict[str, Any]) -> HandoffRecord:
    return HandoffRecord(
        handoff_id=str(payload["handoff_id"]),
        project_id=str(payload["project_id"]),
        work_package_id=str(payload["work_package_id"]),
        stage=str(payload["stage"]),
        producer_profile=str(payload["producer_profile"]),
        stage_outcome=str(payload["stage_outcome"]),
        artifact_refs=tuple(str(value) for value in payload["artifact_refs"]),
        evidence_refs=tuple(str(value) for value in payload["evidence_refs"]),
        evidence_states=tuple(str(value) for value in payload["evidence_states"]),
        finding_state=str(payload["finding_state"]),
        next_stage_prerequisites=tuple(
            bool(value) for value in payload["next_stage_prerequisites"]
        ),
        context_revision=str(payload["context_revision"]),
        candidate_identity=(
            str(payload["candidate_identity"])
            if payload["candidate_identity"] is not None
            else None
        ),
        candidate_identity_required=bool(payload["candidate_identity_required"]),
        independent_review_required=bool(payload["independent_review_required"]),
        independent_review_state=(
            str(payload["independent_review_state"])
            if payload["independent_review_state"] is not None
            else None
        ),
    )
