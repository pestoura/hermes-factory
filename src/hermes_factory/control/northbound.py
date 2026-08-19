from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hermes_factory.traceability.registry import SemanticRegistry


class NorthboundOrigin(StrEnum):
    EXTERNAL = "EXTERNAL"
    INTERNAL_PROFILE = "INTERNAL_PROFILE"


@dataclass(frozen=True)
class NorthboundCaller:
    principal: str
    origin: NorthboundOrigin


class NorthboundAccessDenied(PermissionError):
    pass


class NorthboundControl:
    """Transport-neutral read surface for authorized external Factory clients."""

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
