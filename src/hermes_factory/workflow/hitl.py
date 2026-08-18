from dataclasses import dataclass
from enum import StrEnum

from hermes_factory.traceability import EntityConflict, SemanticRegistry
from hermes_factory.traceability.atomic import record_entity_version_once


class HITLState(StrEnum):
    PENDING = "PENDING"
    DECIDED = "DECIDED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class HITLRequest:
    request_id: str
    request_version: int
    context_revision: str
    candidate_revision: str | None
    allowed_responder: str
    state: HITLState


@dataclass(frozen=True)
class HumanDecision:
    request_id: str
    request_version: int
    context_revision: str
    candidate_revision: str | None
    responder_identity: str
    decision: str


class HITLDecisionCommitError(RuntimeError):
    pass


class HITLDecisionService:
    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def commit(self, request: HITLRequest, decision: HumanDecision) -> HumanDecision:
        if not validate_human_decision(request, decision):
            raise HITLDecisionCommitError("HITL decision is stale, invalid, or unauthorized")
        if not decision.decision.strip():
            raise HITLDecisionCommitError("HITL decision value is required")

        entity_id = f"HumanDecision:{request.request_id}"
        revision = str(request.request_version)
        payload = {
            "request_id": decision.request_id,
            "request_version": decision.request_version,
            "context_revision": decision.context_revision,
            "candidate_revision": decision.candidate_revision,
            "responder_identity": decision.responder_identity,
            "decision": decision.decision,
        }
        event_payload = {
            "request_id": decision.request_id,
            "request_version": decision.request_version,
            "responder_identity": decision.responder_identity,
            "decision": decision.decision,
        }
        try:
            created = record_entity_version_once(
                self._registry,
                entity_id,
                entity_type="HumanDecision",
                revision=revision,
                payload=payload,
                event_id=f"human-decision:{request.request_id}:{request.request_version}",
                event_kind="HUMAN_DECISION_RECORDED",
                event_payload=event_payload,
            )
        except EntityConflict as error:
            raise HITLDecisionCommitError("HITL decision persistence conflict") from error
        if not created:
            raise HITLDecisionCommitError("HITL decision replay rejected")
        return decision


def validate_human_decision(request: HITLRequest, decision: HumanDecision) -> bool:
    if request.state is not HITLState.PENDING:
        return False
    return (
        decision.request_id == request.request_id
        and decision.request_version == request.request_version
        and decision.context_revision == request.context_revision
        and decision.candidate_revision == request.candidate_revision
        and decision.responder_identity == request.allowed_responder
        and bool(decision.decision.strip())
    )
