from enum import StrEnum


class EvidenceState(StrEnum):
    PASS = "PASS"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    ABSENT = "ABSENT"
    STALE = "STALE"


class UATState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"
    STALE = "STALE"


class HandoffState(StrEnum):
    WORKING = "WORKING"
    HANDOFF_PENDING = "HANDOFF_PENDING"
    HANDOFF_READY = "HANDOFF_READY"
    HANDOFF_BLOCKED = "HANDOFF_BLOCKED"
    HANDED_OFF = "HANDED_OFF"
    STALE = "STALE"


def can_satisfy_acceptance(state: EvidenceState) -> bool:
    return state is EvidenceState.PASS


def can_promote_handoff(state: HandoffState) -> bool:
    return state is HandoffState.HANDOFF_READY
