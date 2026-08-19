from collections.abc import Iterable
from enum import StrEnum

from hermes_factory.traceability import SemanticRegistry


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


class ExactSHAEvidenceGate:
    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        candidate_sha: str | None,
        required_evidence_ids: Iterable[str],
    ) -> ExactSHAState:
        evidence_ids = tuple(required_evidence_ids)
        if not evidence_ids:
            return ExactSHAState.EVIDENCE_ABSENT

        records: list[dict[str, object]] = []
        for evidence_id in evidence_ids:
            try:
                record = self._registry.get_evidence(evidence_id)
            except KeyError:
                return ExactSHAState.EVIDENCE_ABSENT
            records.append(record)

        if any(record.get("state") == "STALE" for record in records):
            return ExactSHAState.EVIDENCE_STALE

        identities: list[str | None] = []
        for record in records:
            identity = record.get("candidate")
            if identity is None:
                identities.append(None)
            elif isinstance(identity, str):
                identities.append(identity)
            else:
                return ExactSHAState.IDENTITY_UNKNOWN

        return evaluate_exact_sha(candidate_sha, identities)

    def transition_candidate(
        self,
        *,
        previous_candidate: str,
        new_candidate: str,
    ) -> int:
        if previous_candidate == new_candidate:
            return 0
        return self._registry.mark_evidence_stale_for_candidate(previous_candidate)