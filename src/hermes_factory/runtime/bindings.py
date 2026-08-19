from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hermes_factory.runtime.admission import (
    AdmissionEvidenceState,
    RuntimeComponent,
)


class ExternalVerificationState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED_EXTERNAL_BILLING = "BLOCKED_EXTERNAL_BILLING"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    ABSENT = "ABSENT"


@dataclass(frozen=True)
class RuntimeComponentBinding:
    component: RuntimeComponent
    repository: str
    pull_request: int
    candidate_sha: str
    verification_state: ExternalVerificationState

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> RuntimeComponentBinding:
        if payload.get("schema") != "hermes.factory/runtime-component-binding/v1":
            raise ValueError("unsupported runtime component binding schema")
        repository = payload.get("repository")
        pull_request = payload.get("pull_request")
        candidate_sha = payload.get("candidate_sha")
        if not isinstance(repository, str) or not repository.strip():
            raise ValueError("repository is required")
        if not isinstance(pull_request, int) or pull_request <= 0:
            raise ValueError("pull_request must be a positive integer")
        if not isinstance(candidate_sha, str) or len(candidate_sha) != 40:
            raise ValueError("candidate_sha must be a 40-character commit SHA")
        return cls(
            component=RuntimeComponent(str(payload.get("component"))),
            repository=repository,
            pull_request=pull_request,
            candidate_sha=candidate_sha,
            verification_state=ExternalVerificationState(
                str(payload.get("verification_state"))
            ),
        )

    @property
    def admission_state(self) -> AdmissionEvidenceState:
        mapping = {
            ExternalVerificationState.PASS: AdmissionEvidenceState.PASS,
            ExternalVerificationState.FAIL: AdmissionEvidenceState.FAIL,
            ExternalVerificationState.BLOCKED_EXTERNAL_BILLING: AdmissionEvidenceState.BLOCKED,
            ExternalVerificationState.NOT_RUN: AdmissionEvidenceState.NOT_RUN,
            ExternalVerificationState.UNKNOWN: AdmissionEvidenceState.UNKNOWN,
            ExternalVerificationState.STALE: AdmissionEvidenceState.STALE,
            ExternalVerificationState.ABSENT: AdmissionEvidenceState.ABSENT,
        }
        return mapping[self.verification_state]

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/runtime-component-binding/v1",
            "component": self.component.value,
            "repository": self.repository,
            "pull_request": self.pull_request,
            "candidate_sha": self.candidate_sha,
            "verification_state": self.verification_state.value,
            "admission_state": self.admission_state.value,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_manifest(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
