from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass


class JarvasOperationsAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class JarvasOperationsEvidence:
    source: str
    evidence_id: str
    generated_at: str
    scope: str
    mode: str
    run_outcome: str
    overall_status: str
    required_status: str
    optional_status: str
    attempted_recoveries: int
    blocked_actions: int
    unresolved_findings: int
    report_digest: str
    read_only: bool = True


class JarvasOperationsEvidenceAdapter:
    def consume(self, report: dict[str, object]) -> JarvasOperationsEvidence:
        schema = report.get("schema_version")
        if not isinstance(schema, int) or isinstance(schema, bool) or schema != 1:
            raise JarvasOperationsAdapterError(
                "unsupported Jarvas Operations report schema_version"
            )

        evidence_id = self._text(report.get("evidence_id"), "evidence_id")
        if re.fullmatch(r"[0-9a-fA-F]{16}", evidence_id) is None:
            raise JarvasOperationsAdapterError(
                "Jarvas Operations evidence_id must be a 16-hex identity"
            )
        generated_at = self._text(report.get("generated_at"), "generated_at")
        mode = self._text(report.get("mode"), "mode")
        run_outcome = self._text(report.get("run_outcome"), "run_outcome")
        overall_status = self._text(report.get("overall_status"), "overall_status")
        required_status = self._text(report.get("required_status"), "required_status")
        optional_status = self._text(report.get("optional_status"), "optional_status")

        metadata = self._mapping(report.get("metadata"), "metadata")
        tool = self._text(metadata.get("tool"), "metadata.tool")
        if tool != "jarvas-operations":
            raise JarvasOperationsAdapterError(
                "Jarvas Operations metadata.tool identity does not match"
            )
        scope = self._text(metadata.get("scope"), "metadata.scope")

        if run_outcome != "complete" and overall_status == "healthy":
            raise JarvasOperationsAdapterError(
                "incomplete Jarvas Operations run cannot be treated as healthy"
            )

        attempted_recoveries = self._list_count(
            report.get("attempted_recoveries"),
            "attempted_recoveries",
        )
        blocked_actions = self._list_count(report.get("blocked_actions"), "blocked_actions")
        unresolved_findings = self._list_count(
            report.get("unresolved_findings"),
            "unresolved_findings",
        )

        return JarvasOperationsEvidence(
            source="JARVAS_OPERATIONS_REPORT",
            evidence_id=evidence_id.lower(),
            generated_at=generated_at,
            scope=scope,
            mode=mode,
            run_outcome=run_outcome,
            overall_status=overall_status,
            required_status=required_status,
            optional_status=optional_status,
            attempted_recoveries=attempted_recoveries,
            blocked_actions=blocked_actions,
            unresolved_findings=unresolved_findings,
            report_digest=self._digest(report),
        )

    @staticmethod
    def _text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise JarvasOperationsAdapterError(
                f"Jarvas Operations {label} must be a non-empty string"
            )
        return value.strip()

    @staticmethod
    def _mapping(value: object, label: str) -> dict[str, object]:
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise JarvasOperationsAdapterError(
                f"Jarvas Operations {label} must be a string-keyed mapping"
            )
        return {str(key): item for key, item in value.items()}

    @staticmethod
    def _list_count(value: object, label: str) -> int:
        if not isinstance(value, list):
            raise JarvasOperationsAdapterError(
                f"Jarvas Operations {label} must be a list"
            )
        return len(value)

    @staticmethod
    def _digest(report: Mapping[str, object]) -> str:
        try:
            encoded = json.dumps(
                report,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise JarvasOperationsAdapterError(
                "Jarvas Operations report is not canonically serializable"
            ) from error
        return hashlib.sha256(encoded).hexdigest()
