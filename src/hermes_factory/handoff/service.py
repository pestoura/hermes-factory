from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hermes_factory.domain import HandoffState


@dataclass(frozen=True)
class HandoffRecord:
    handoff_id: str
    project_id: str
    work_package_id: str
    stage: str
    producer_profile: str
    stage_outcome: str
    artifact_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evidence_states: tuple[str, ...]
    finding_state: str
    next_stage_prerequisites: tuple[bool, ...]
    context_revision: str
    candidate_identity: str | None
    candidate_identity_required: bool
    independent_review_required: bool
    independent_review_state: str | None

    def validate(self) -> None:
        required = {
            "handoff_id": self.handoff_id,
            "project_id": self.project_id,
            "work_package_id": self.work_package_id,
            "stage": self.stage,
            "producer_profile": self.producer_profile,
            "stage_outcome": self.stage_outcome,
            "context_revision": self.context_revision,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not self.artifact_refs:
            raise ValueError("artifact_refs are required")
        if not self.evidence_refs:
            raise ValueError("evidence_refs are required")
        if len(self.evidence_refs) != len(self.evidence_states):
            raise ValueError("evidence_refs and evidence_states must have equal length")


class HandoffLedger(Protocol):
    def commit(self, record: HandoffRecord, state: HandoffState) -> None: ...

    def set_state(self, handoff_id: str, state: HandoffState) -> None: ...


class KanbanAuthorizer(Protocol):
    def authorize_dispatch(
        self,
        *,
        board: str,
        task_id: str,
        actor: str,
        source: str,
    ) -> None: ...


class HandoffService:
    """Evaluate and promote immutable handoff evidence into native dispatch approval."""

    def __init__(self, *, ledger: HandoffLedger, kanban: KanbanAuthorizer) -> None:
        self._ledger = ledger
        self._kanban = kanban

    def promote(
        self,
        record: HandoffRecord,
        *,
        current_context_revision: str,
        current_candidate_identity: str | None,
        next_board: str,
        next_task_id: str,
        actor: str,
    ) -> HandoffState:
        record.validate()

        if record.context_revision != current_context_revision:
            return self._commit_terminal(record, HandoffState.STALE)
        if (
            record.candidate_identity is not None
            and record.candidate_identity != current_candidate_identity
        ):
            return self._commit_terminal(record, HandoffState.STALE)

        if not self._is_ready(record):
            return self._commit_terminal(record, HandoffState.HANDOFF_BLOCKED)

        # Phase 1: durable semantic proof. If native authorization fails, this
        # stays HANDOFF_READY and can be retried without fabricating completion.
        self._ledger.commit(record, HandoffState.HANDOFF_READY)

        # Phase 2: Hermes owns dispatch. The Factory only grants the structured
        # authorization after the complete handoff record is already durable.
        self._kanban.authorize_dispatch(
            board=next_board,
            task_id=next_task_id,
            actor=actor,
            source="factory-continuous-handoff",
        )
        self._ledger.set_state(record.handoff_id, HandoffState.HANDED_OFF)
        return HandoffState.HANDED_OFF

    def _commit_terminal(self, record: HandoffRecord, state: HandoffState) -> HandoffState:
        self._ledger.commit(record, state)
        return state

    @staticmethod
    def _is_ready(record: HandoffRecord) -> bool:
        if record.stage_outcome != "PASS":
            return False
        if record.candidate_identity_required and not record.candidate_identity:
            return False
        if any(state != "PASS" for state in record.evidence_states):
            return False
        if record.finding_state not in {"NONE", "RESOLVED"}:
            return False
        if not record.next_stage_prerequisites or not all(record.next_stage_prerequisites):
            return False
        return not (
            record.independent_review_required
            and record.independent_review_state != "PASS"
        )
