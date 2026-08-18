from dataclasses import dataclass
from enum import StrEnum


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


def validate_human_decision(request: HITLRequest, decision: HumanDecision) -> bool:
    if request.state is not HITLState.PENDING:
        return False
    return (
        decision.request_id == request.request_id
        and decision.request_version == request.request_version
        and decision.context_revision == request.context_revision
        and decision.candidate_revision == request.candidate_revision
        and decision.responder_identity == request.allowed_responder
    )
