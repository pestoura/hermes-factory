from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hermes_factory.traceability.registry import SemanticRegistry


class NorthboundOrigin(StrEnum):
    EXTERNAL = "EXTERNAL"
    INTERNAL_PROFILE = "INTERNAL_PROFILE"


class ProtectedMutationAction(StrEnum):
    MERGE_PR = "MERGE_PR"
    RELEASE = "RELEASE"
    ACTIVATE_PROFILE = "ACTIVATE_PROFILE"
    ACTIVATE_SKILL = "ACTIVATE_SKILL"


@dataclass(frozen=True)
class NorthboundCaller:
    principal: str
    origin: NorthboundOrigin


class NorthboundAccessDenied(PermissionError):
    pass


class NorthboundMutationDenied(RuntimeError):
    pass


class NorthboundControl:
    """Transport-neutral external governance/control surface for the Factory."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, registry: SemanticRegistry) -> None:
        self._registry = registry

    def status(
        self,
        *,
        candidate_sha: str,
        caller: NorthboundCaller,
    ) -> dict[str, Any]:
        self._authorize(candidate_sha=candidate_sha, caller=caller)
        evidence = self._registry.list_evidence(candidate=candidate_sha)
        states = Counter(str(row["state"]) for row in evidence)
        return self._response(
            operation="STATUS",
            candidate_sha=candidate_sha,
            data={
                "projects": self._registry.list_latest_entities("Project"),
                "work_packages": self._registry.list_latest_entities("WorkPackage"),
                "evidence_states": dict(sorted(states.items())),
            },
        )

    def evidence(
        self,
        *,
        candidate_sha: str,
        caller: NorthboundCaller,
    ) -> dict[str, Any]:
        self._authorize(candidate_sha=candidate_sha, caller=caller)
        return self._response(
            operation="EVIDENCE",
            candidate_sha=candidate_sha,
            data={"records": self._registry.list_evidence(candidate=candidate_sha)},
        )

    def acceptance(
        self,
        *,
        candidate_sha: str,
        caller: NorthboundCaller,
    ) -> dict[str, Any]:
        self._authorize(candidate_sha=candidate_sha, caller=caller)
        records = [
            row
            for row in self._registry.list_latest_entities("AcceptanceDecision")
            if self._candidate_from_entity(row) == candidate_sha
        ]
        return self._response(
            operation="ACCEPTANCE",
            candidate_sha=candidate_sha,
            data={"records": records},
        )

    def protected_mutation_intent(
        self,
        *,
        action: ProtectedMutationAction,
        resource: str,
        candidate_sha: str,
        caller: NorthboundCaller,
        authority_evidence_id: str,
        human_decision_id: str,
    ) -> dict[str, Any]:
        self._authorize(candidate_sha=candidate_sha, caller=caller)
        if not resource.strip():
            raise ValueError("protected mutation resource is required")
        authority = self._authority_evidence(
            authority_evidence_id,
            candidate_sha=candidate_sha,
        )
        decision = self._human_decision(
            human_decision_id,
            candidate_sha=candidate_sha,
        )
        payload: dict[str, Any] = {
            "action": action.value,
            "resource": resource,
            "principal": caller.principal,
            "candidate_sha": candidate_sha,
            "authority_evidence_id": str(authority["evidence_id"]),
            "human_decision_id": str(decision["entity_id"]),
            "execute": False,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["intent_id"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return self._response(
            operation="PROTECTED_MUTATION_INTENT",
            candidate_sha=candidate_sha,
            data=payload,
        )

    def _authority_evidence(
        self,
        evidence_id: str,
        *,
        candidate_sha: str,
    ) -> dict[str, Any]:
        try:
            evidence = self._registry.get_evidence(evidence_id)
        except KeyError as exc:
            raise NorthboundMutationDenied("authority evidence is absent") from exc
        if evidence.get("state") != "PASS" or evidence.get("candidate") != candidate_sha:
            raise NorthboundMutationDenied(
                "authority evidence is not PASS and bound to candidate"
            )
        return evidence

    def _human_decision(
        self,
        entity_id: str,
        *,
        candidate_sha: str,
    ) -> dict[str, Any]:
        matches = [
            row
            for row in self._registry.list_latest_entities("HumanDecision")
            if row.get("entity_id") == entity_id
        ]
        if len(matches) != 1:
            raise NorthboundMutationDenied("HumanDecision is absent")
        decision = matches[0]
        payload = decision.get("payload")
        if not isinstance(payload, dict) or payload.get("candidate_revision") != candidate_sha:
            raise NorthboundMutationDenied("HumanDecision is not bound to candidate")
        if not isinstance(payload.get("decision"), str) or not str(payload["decision"]).strip():
            raise NorthboundMutationDenied("HumanDecision is invalid")
        return decision

    @staticmethod
    def _candidate_from_entity(row: dict[str, Any]) -> str | None:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            return None
        candidate = payload.get("candidate_sha")
        return candidate if isinstance(candidate, str) else None

    @staticmethod
    def _authorize(*, candidate_sha: str, caller: NorthboundCaller) -> None:
        if not candidate_sha.strip():
            raise ValueError("candidate_sha is required")
        if not caller.principal.strip():
            raise ValueError("northbound principal is required")
        if caller.origin is not NorthboundOrigin.EXTERNAL:
            raise NorthboundAccessDenied("internal profiles cannot use northbound control")

    @classmethod
    def _response(
        cls,
        *,
        operation: str,
        candidate_sha: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": cls.SCHEMA_VERSION,
            "operation": operation,
            "candidate_sha": candidate_sha,
            "data": data,
        }
