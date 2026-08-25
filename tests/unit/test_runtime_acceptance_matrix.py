import pytest

from hermes_factory.runtime.admission import AdmissionEvidenceState


def _acceptance_contract():
    try:
        from hermes_factory.governance.runtime_acceptance import (
            RuntimeAcceptanceEvidence,
            RuntimeAcceptanceMatrix,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("Phase Q runtime acceptance matrix is not implemented") from exc
    return RuntimeAcceptanceEvidence, RuntimeAcceptanceMatrix


def test_phase_q_matrix_contains_all_sixteen_required_scenarios_and_starts_not_run() -> None:
    _, matrix_type = _acceptance_contract()
    matrix = matrix_type(candidate_sha="a" * 40)

    assessment = matrix.assess(())

    assert len(matrix.scenarios) == 16
    assert "superseded_generation_retirement_preserves_history" in matrix.scenarios
    assert assessment.accepted_runtime is False
    assert set(assessment.scenario_states.values()) == {AdmissionEvidenceState.NOT_RUN}
    assert len(assessment.blockers) == 16
    assert assessment.to_manifest()["candidate_sha"] == "a" * 40
    assert len(assessment.digest) == 64


def test_phase_q_requires_exact_candidate_sha_for_every_scenario() -> None:
    evidence_type, matrix_type = _acceptance_contract()
    matrix = matrix_type(candidate_sha="a" * 40)
    evidence = evidence_type(
        scenario=matrix.scenarios[0],
        candidate_sha="b" * 40,
        state=AdmissionEvidenceState.PASS,
        evidence_ref="runtime://scenario/1",
    )

    with pytest.raises(ValueError, match="candidate SHA"):
        matrix.assess((evidence,))


def test_phase_q_accepts_runtime_only_when_all_sixteen_scenarios_pass() -> None:
    evidence_type, matrix_type = _acceptance_contract()
    matrix = matrix_type(candidate_sha="a" * 40)
    evidence = tuple(
        evidence_type(
            scenario=scenario,
            candidate_sha="a" * 40,
            state=AdmissionEvidenceState.PASS,
            evidence_ref=f"runtime://{scenario}",
        )
        for scenario in matrix.scenarios
    )

    assessment = matrix.assess(evidence)

    assert assessment.accepted_runtime is True
    assert assessment.blockers == ()
    assert set(assessment.scenario_states.values()) == {AdmissionEvidenceState.PASS}


@pytest.mark.parametrize("state_name", ["FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "STALE", "ABSENT"])
def test_phase_q_never_collapses_non_pass_to_accepted_runtime(state_name: str) -> None:
    evidence_type, matrix_type = _acceptance_contract()
    matrix = matrix_type(candidate_sha="a" * 40)
    state = AdmissionEvidenceState[state_name]
    evidence = tuple(
        evidence_type(
            scenario=scenario,
            candidate_sha="a" * 40,
            state=(state if index == 0 else AdmissionEvidenceState.PASS),
            evidence_ref=f"runtime://{scenario}",
        )
        for index, scenario in enumerate(matrix.scenarios)
    )

    assessment = matrix.assess(evidence)

    assert assessment.accepted_runtime is False
    assert assessment.scenario_states[matrix.scenarios[0]] is state


def test_phase_q_rejects_duplicate_or_unknown_scenario_evidence() -> None:
    evidence_type, matrix_type = _acceptance_contract()
    matrix = matrix_type(candidate_sha="a" * 40)
    first = evidence_type(
        scenario=matrix.scenarios[0],
        candidate_sha="a" * 40,
        state=AdmissionEvidenceState.PASS,
        evidence_ref="runtime://first",
    )
    duplicate = evidence_type(
        scenario=matrix.scenarios[0],
        candidate_sha="a" * 40,
        state=AdmissionEvidenceState.PASS,
        evidence_ref="runtime://duplicate",
    )
    unknown = evidence_type(
        scenario="unknown-runtime-scenario",
        candidate_sha="a" * 40,
        state=AdmissionEvidenceState.PASS,
        evidence_ref="runtime://unknown",
    )

    with pytest.raises(ValueError, match="duplicate"):
        matrix.assess((first, duplicate))
    with pytest.raises(ValueError, match="unknown"):
        matrix.assess((unknown,))
