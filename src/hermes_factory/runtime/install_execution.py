from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.install import ControlledInstallPlan, InstallOperation


class InstallExecutionError(ValueError):
    pass


class InstallRuntime(Protocol):
    """Mutation boundary supplied by the controlled runtime environment.

    The Factory executor owns ordering, authorization and compensation semantics;
    the concrete Hermes/Jarvas runtime adapter owns how each structured
    InstallOperation is preflighted, applied and rolled back.
    """

    def preflight(self, operations: tuple[InstallOperation, ...]) -> None: ...

    def apply(self, operation: InstallOperation) -> str: ...

    def rollback(self, operation: InstallOperation, receipt: str) -> None: ...


@dataclass(frozen=True)
class InstallExecutionAuthorization:
    plan_digest: str
    approved_by: str
    evidence_ref: str


@dataclass(frozen=True)
class InstallExecutionReport:
    plan_digest: str
    authorization_evidence_ref: str
    state: str
    applied_count: int
    rolled_back_count: int
    failure: str
    rollback_failures: tuple[str, ...]
    execute: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/install-execution-report/v1",
            "plan_digest": self.plan_digest,
            "authorization_evidence_ref": self.authorization_evidence_ref,
            "state": self.state,
            "applied_count": self.applied_count,
            "rolled_back_count": self.rolled_back_count,
            "failure": self.failure,
            "rollback_failures": list(self.rollback_failures),
            "execute": self.execute,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_manifest(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class InstallExecutor:
    def __init__(self, runtime: InstallRuntime) -> None:
        self._runtime = runtime

    @staticmethod
    def _authorize(
        plan: ControlledInstallPlan,
        authorization: InstallExecutionAuthorization,
    ) -> None:
        if (
            not plan.ready_for_controlled_execution
            or plan.execution_state != "READY"
            or plan.blockers
        ):
            raise InstallExecutionError("controlled install plan is not READY")
        if authorization.plan_digest != plan.digest:
            raise InstallExecutionError("authorization plan digest does not match current plan")
        if not authorization.approved_by.strip() or not authorization.evidence_ref.strip():
            raise InstallExecutionError("explicit approval provenance is required")

    @staticmethod
    def _validate_source_identities(plan: ControlledInstallPlan) -> None:
        for operation in plan.operations:
            if operation.source_digest is None:
                continue
            if operation.source is None or not operation.source.strip():
                raise InstallExecutionError(
                    f"digest-bound install source is absent for "
                    f"{operation.component.value}:{operation.action}"
                )
            try:
                observed_digest = digest_artifact(Path(operation.source))
            except (OSError, ValueError) as exc:
                raise InstallExecutionError(
                    f"install source digest unavailable for "
                    f"{operation.component.value}:{operation.action}"
                ) from exc
            if observed_digest != operation.source_digest:
                raise InstallExecutionError(
                    f"install source digest drift for "
                    f"{operation.component.value}:{operation.action}: "
                    f"expected={operation.source_digest} observed={observed_digest}"
                )

    def _preflight_runtime(self, plan: ControlledInstallPlan) -> None:
        try:
            self._runtime.preflight(plan.operations)
        except (RuntimeError, OSError, ValueError) as exc:
            raise InstallExecutionError(f"runtime preflight failed: {exc}") from exc

    def execute(
        self,
        plan: ControlledInstallPlan,
        authorization: InstallExecutionAuthorization,
    ) -> InstallExecutionReport:
        self._authorize(plan, authorization)
        self._validate_source_identities(plan)
        self._preflight_runtime(plan)

        applied: list[tuple[InstallOperation, str]] = []
        try:
            for operation in plan.operations:
                receipt = self._runtime.apply(operation)
                if not isinstance(receipt, str) or not receipt.strip():
                    raise RuntimeError(
                        f"runtime returned no receipt for {operation.component.value}:"
                        f"{operation.action}"
                    )
                applied.append((operation, receipt))
        except (RuntimeError, OSError, ValueError) as exc:
            rollback_failures: list[str] = []
            rolled_back_count = 0
            for operation, receipt in reversed(applied):
                try:
                    self._runtime.rollback(operation, receipt)
                    rolled_back_count += 1
                except (RuntimeError, OSError, ValueError) as rollback_exc:
                    rollback_failures.append(
                        f"{operation.component.value}:{operation.action}: {rollback_exc}"
                    )
            return InstallExecutionReport(
                plan_digest=plan.digest,
                authorization_evidence_ref=authorization.evidence_ref,
                state="ROLLBACK_FAILED" if rollback_failures else "ROLLED_BACK",
                applied_count=len(applied),
                rolled_back_count=rolled_back_count,
                failure=str(exc),
                rollback_failures=tuple(rollback_failures),
                execute=True,
            )

        return InstallExecutionReport(
            plan_digest=plan.digest,
            authorization_evidence_ref=authorization.evidence_ref,
            state="PASS",
            applied_count=len(applied),
            rolled_back_count=0,
            failure="",
            rollback_failures=(),
            execute=True,
        )
