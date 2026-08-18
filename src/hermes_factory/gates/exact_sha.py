from enum import StrEnum
from typing import Iterable


class ExactSHAState(StrEnum):
    SHA_MATCH = "SHA_MATCH"
    SHA_MISMATCH = "SHA_MISMATCH"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_ABSENT = "EVIDENCE_ABSENT"
    IDENTITY_UNKNOWN = "IDENTITY_UNKNOWN"


def evaluate_exact_sha(
    candidate_sha: str | None,
    evidence_shas: Iterable[str | None],
    *,
    stale: bool = False,
) -> ExactSHAState:
    if stale:
        return ExactSHAState.EVIDENCE_STALE
    if candidate_sha is None or not candidate_sha.strip():
        return ExactSHAState.IDENTITY_UNKNOWN
    identities = list(evidence_shas)
    if not identities:
        return ExactSHAState.EVIDENCE_ABSENT
    if any(identity is None or not str(identity).strip() for identity in identities):
        return ExactSHAState.IDENTITY_UNKNOWN
    if all(identity == candidate_sha for identity in identities):
        return ExactSHAState.SHA_MATCH
    return ExactSHAState.SHA_MISMATCH
