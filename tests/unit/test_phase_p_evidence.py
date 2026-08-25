from __future__ import annotations

import json
from pathlib import Path

import pytest

CANDIDATE = "a" * 40
HERMES_SHA = "b" * 40


def _plan(action: str):
    from hermes_factory.runtime.admission import RuntimeComponent
    from hermes_factory.runtime.install import ControlledInstallPlan, InstallOperation

    return ControlledInstallPlan(
        accepted_hermes_sha=HERMES_SHA,
        observed_hermes_sha=HERMES_SHA,
        factory_candidate_sha=CANDIDATE,
        operations=(
            InstallOperation(
                component=RuntimeComponent.FACTORY_PACKAGE,
                action=action,
                target="HERMES_RUNTIME_ENV",
            ),
        ),
        blockers=(),
        execution_state="READY",
        ready_for_controlled_execution=True,
        execute=True,
    )


def _store_contract():
    module = __import__(
        "hermes_factory.runtime.phase_p_evidence",
        fromlist=["PhasePEvidenceError", "PhasePEvidenceStore"],
    )
    return module.PhasePEvidenceError, module.PhasePEvidenceStore


def _report(
    plan,
    *,
    plan_digest: str | None = None,
    evidence_ref: str = "chat://approval",
    state: str = "PASS",
    execute: bool = True,
):
    from hermes_factory.runtime.install_execution import InstallExecutionReport

    return InstallExecutionReport(
        plan_digest=plan.digest if plan_digest is None else plan_digest,
        authorization_evidence_ref=evidence_ref,
        state=state,
        applied_count=len(plan.operations),
        rolled_back_count=0,
        failure="",
        rollback_failures=(),
        execute=execute,
    )


def test_different_phase_p_plans_for_same_candidate_never_overwrite_prior_evidence(
    tmp_path: Path,
) -> None:
    _, store_type = _store_contract()
    store = store_type(tmp_path, candidate_sha=CANDIDATE)
    first = _plan("FIRST")
    second = _plan("SECOND")

    first_dir = store.persist_plan(first)
    original = (first_dir / "controlled-install-plan.json").read_bytes()
    second_dir = store.persist_plan(second)

    assert first_dir != second_dir
    assert first_dir.name == first.digest
    assert second_dir.name == second.digest
    assert (first_dir / "controlled-install-plan.json").read_bytes() == original
    assert (first_dir / "plan-digest.txt").read_text().strip() == first.digest
    assert json.loads((second_dir / "controlled-install-plan.json").read_text())[
        "factory_candidate_sha"
    ] == CANDIDATE


def test_terminal_report_is_bound_to_plan_digest_and_write_once(tmp_path: Path) -> None:
    error_type, store_type = _store_contract()
    store = store_type(tmp_path, candidate_sha=CANDIDATE)
    plan = _plan("INSTALL")
    run_dir = store.persist_plan(plan)
    report_path = run_dir / "install-execution-report.json"

    with pytest.raises(error_type, match="plan digest"):
        store.persist_report(plan, _report(plan, plan_digest="0" * 64))
    assert not report_path.exists()

    report = _report(plan)
    assert store.persist_report(plan, report) == report_path
    original = report_path.read_bytes()
    assert json.loads(original)["plan_digest"] == plan.digest
    assert store.persist_report(plan, report) == report_path
    assert report_path.read_bytes() == original

    report_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(error_type, match="immutable"):
        store.persist_report(plan, report)


@pytest.mark.parametrize(
    ("state", "execute"),
    (("READY", True), ("PASS", False)),
)
def test_only_terminal_executed_reports_can_be_persisted(
    tmp_path: Path,
    state: str,
    execute: bool,
) -> None:
    error_type, store_type = _store_contract()
    store = store_type(tmp_path, candidate_sha=CANDIDATE)
    plan = _plan("INSTALL")
    run_dir = store.persist_plan(plan)
    report_path = run_dir / "install-execution-report.json"

    with pytest.raises(error_type, match="terminal"):
        store.persist_report(plan, _report(plan, state=state, execute=execute))
    assert not report_path.exists()
