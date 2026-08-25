from __future__ import annotations

import json
import re
from pathlib import Path

from hermes_factory.runtime.install import ControlledInstallPlan
from hermes_factory.runtime.install_execution import InstallExecutionReport

_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_TERMINAL_REPORT_STATES = frozenset({"PASS", "ROLLED_BACK", "ROLLBACK_FAILED"})


class PhasePEvidenceError(ValueError):
    pass


class PhasePEvidenceStore:
    """Write-once evidence store for controlled Phase P installation runs."""

    def __init__(self, evidence_root: Path, *, candidate_sha: str) -> None:
        if not _GIT_SHA.fullmatch(candidate_sha):
            raise PhasePEvidenceError("candidate SHA must be an exact 40-character Git SHA")
        self._evidence_root = Path(evidence_root)
        self._candidate_sha = candidate_sha.lower()

    def persist_plan(self, plan: ControlledInstallPlan) -> Path:
        if plan.factory_candidate_sha.lower() != self._candidate_sha:
            raise PhasePEvidenceError("Phase P plan candidate does not match evidence candidate")

        run_dir = (
            self._evidence_root
            / self._candidate_sha
            / "phase-p"
            / "runs"
            / plan.digest
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        plan_payload = (
            json.dumps(plan.to_manifest(), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        self._write_once(
            run_dir / "controlled-install-plan.json",
            plan_payload,
            "Phase P plan evidence",
        )
        self._write_once(
            run_dir / "plan-digest.txt",
            (plan.digest + "\n").encode("utf-8"),
            "Phase P plan digest evidence",
        )
        return run_dir

    def persist_report(
        self,
        plan: ControlledInstallPlan,
        report: InstallExecutionReport,
    ) -> Path:
        if plan.factory_candidate_sha.lower() != self._candidate_sha:
            raise PhasePEvidenceError("Phase P plan candidate does not match evidence candidate")
        if report.plan_digest != plan.digest:
            raise PhasePEvidenceError(
                "Phase P report plan digest does not match immutable plan digest"
            )
        if report.state not in _TERMINAL_REPORT_STATES or not report.execute:
            raise PhasePEvidenceError(
                "Phase P execution report must represent a terminal executed state"
            )

        run_dir = self.persist_plan(plan)
        report_path = run_dir / "install-execution-report.json"
        report_payload = (
            json.dumps(report.to_manifest(), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        self._write_once(
            report_path,
            report_payload,
            "Phase P execution report evidence",
        )
        return report_path

    @staticmethod
    def _write_once(path: Path, payload: bytes, label: str) -> None:
        try:
            with path.open("xb") as handle:
                handle.write(payload)
            return
        except FileExistsError:
            pass

        if path.is_symlink() or not path.is_file():
            raise PhasePEvidenceError(f"{label} must be an immutable regular file")
        if path.read_bytes() != payload:
            raise PhasePEvidenceError(f"{label} is immutable and does not match")
