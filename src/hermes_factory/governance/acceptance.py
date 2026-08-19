from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hermes_factory.gates import ExactSHAEvidenceGate, ExactSHAState
from hermes_factory.traceability import SemanticRegistry


class AcceptanceClass(StrEnum):
    REPOSITORY = "REPOSITORY"
    INTEGRATION = "INTEGRATION"
    UAT = "UAT"
    LIVE = "LIVE"
    RELEASE = "RELEASE"


class AcceptanceDecisionState(StrEnum):
    ACCEPTED = "ACCEPTED"
    HOLD = "HOLD"


@dataclass(frozen=True)
class AcceptancePolicy:
    owner_release_required: bool = False
    owner_actor_id: str | None = None


@dataclass(frozen=True)
class AcceptanceRequest:
    decision_id: str
    acceptance_class: AcceptanceClass
    candidate_sha: str
    required_evidence_ids: tuple[str, ...]
    independent_evidence_ids: tuple[str, ...] = ()
    subject_actor_ids: frozenset[str] = frozenset()
    owner_approval_evidence_id: str | None = None


@dataclass(frozen=True)
class AcceptanceDecision:
    decision_id: str
    acceptance_class: AcceptanceClass
    candidate_sha: str
    state: AcceptanceDecisionState
    reason: str
    evidence_ids: tuple[str, ...]


class AcceptanceEngine:
    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry
        self._exact_sha = ExactSHAEvidenceGate(registry)

    def derive(
        self,
        request: AcceptanceRequest,
        *,
        policy: AcceptancePolicy,
    ) -> AcceptanceDecision:
        self._validate_request(request, policy)

        evidence_records: dict[str, dict[str, object]] = {}
        for evidence_id in request.required_evidence_ids:
            try:
                record = self._registry.get_evidence(evidence_id)
            except KeyError:
                return self._hold(request, "required evidence is absent")
            evidence_records[evidence_id] = record
            if record.get("state") != "PASS":
                return self._hold(request, "required evidence is not PASS")

        exact_state = self._exact_sha.evaluate(
            request.candidate_sha,
            request.required_evidence_ids,
        )
        if exact_state is not ExactSHAState.SHA_MATCH:
            return self._hold(request, f"exact-SHA gate is {exact_state.value}")

        for evidence_id in request.independent_evidence_ids:
            record = evidence_records[evidence_id]
            payload = record.get("payload")
            actor_id = payload.get("actor_id") if isinstance(payload, dict) else None
            if not isinstance(actor_id, str) or not actor_id.strip():
                return self._hold(request, "independent evidence actor identity is unknown")
            if actor_id in request.subject_actor_ids:
                return self._hold(request, "separation of duties is not satisfied")

        if request.acceptance_class is AcceptanceClass.RELEASE and policy.owner_release_required:
            owner_result = self._evaluate_owner_release(request, policy)
            if owner_result is not None:
                return owner_result

        decision = AcceptanceDecision(
            decision_id=request.decision_id,
            acceptance_class=request.acceptance_class,
            candidate_sha=request.candidate_sha,
            state=AcceptanceDecisionState.ACCEPTED,
            reason="all required governed evidence satisfied",
            evidence_ids=request.required_evidence_ids,
        )
        self._persist_accepted(decision)
        return decision

    def _evaluate_owner_release(
        self,
        request: AcceptanceRequest,
        policy: AcceptancePolicy,
    ) -> AcceptanceDecision | None:
        evidence_id = request.owner_approval_evidence_id
        if evidence_id is None:
            return self._hold(request, "owner release evidence is required")
        try:
            record = self._registry.get_evidence(evidence_id)
        except KeyError:
            return self._hold(request, "owner release evidence is absent")
        if record.get("state") != "PASS":
            return self._hold(request, "owner release evidence is not PASS")
        if self._exact_sha.evaluate(request.candidate_sha, (evidence_id,)) is not ExactSHAState.SHA_MATCH:
            return self._hold(request, "owner release evidence is not bound to candidate SHA")

        payload = record.get("payload")
        if not isinstance(payload, dict):
            return self._hold(request, "owner release evidence payload is invalid")
        actor_id = payload.get("actor_id")
        if actor_id != policy.owner_actor_id:
            return self._hold(request, "owner release evidence actor is not authorized owner")
        if payload.get("decision") != "APPROVE_RELEASE":
            return self._hold(request, "owner release decision is not APPROVE_RELEASE")
        return None

    @staticmethod
    def _validate_request(
        request: AcceptanceRequest,
        policy: AcceptancePolicy,
    ) -> None:
        if not request.decision_id.strip():
            raise ValueError("acceptance decision_id is required")
        if not request.candidate_sha.strip():
            raise ValueError("acceptance candidate_sha is required")
        if not request.required_evidence_ids:
            raise ValueError("acceptance requires evidence")
        if len(set(request.required_evidence_ids)) != len(request.required_evidence_ids):
            raise ValueError("acceptance evidence ids must be unique")
        if not set(request.independent_evidence_ids).issubset(request.required_evidence_ids):
            raise ValueError("independent evidence must also be required evidence")
        if request.acceptance_class is AcceptanceClass.RELEASE and policy.owner_release_required:
            if policy.owner_actor_id is None or not policy.owner_actor_id.strip():
                raise ValueError("owner_actor_id is required for owner-reserved release")

    @staticmethod
    def _hold(request: AcceptanceRequest, reason: str) -> AcceptanceDecision:
        return AcceptanceDecision(
            decision_id=request.decision_id,
            acceptance_class=request.acceptance_class,
            candidate_sha=request.candidate_sha,
            state=AcceptanceDecisionState.HOLD,
            reason=reason,
            evidence_ids=request.required_evidence_ids,
        )

    def _persist_accepted(self, decision: AcceptanceDecision) -> None:
        self._registry.repository("AcceptanceDecision").put(
            decision.decision_id,
            decision.candidate_sha,
            {
                "acceptance_class": decision.acceptance_class.value,
                "candidate_sha": decision.candidate_sha,
                "evidence_ids": list(decision.evidence_ids),
                "reason": decision.reason,
                "state": decision.state.value,
            },
        )
