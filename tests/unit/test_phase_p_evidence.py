from __future__ import annotations

import json
from pathlib import Path


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


def _store_type():
    module = __import__(
        "hermes_factory.runtime.phase_p_evidence",
        fromlist=["PhasePEvidenceStore"],
    )
    return module.PhasePEvidenceStore


def test_different_phase_p_plans_for_same_candidate_never_overwrite_prior_evidence(
    tmp_path: Path,
) -> None:
    store = _store_type()(tmp_path, candidate_sha=CANDIDATE)
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
