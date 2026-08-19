import pytest


def _runtime_admission_contract():
    try:
        from hermes_factory.runtime.admission import (
            AdmissionEvidenceState,
            RuntimeAdmissionError,
            RuntimeAdmissionPlanner,
            RuntimeComponent,
        )
    except ModuleNotFoundError:
        pytest.fail("Phase P runtime admission contract is not implemented")
    return (
        AdmissionEvidenceState,
        RuntimeAdmissionError,
        RuntimeAdmissionPlanner,
        RuntimeComponent,
    )


def test_runtime_admission_plan_is_bound_to_exact_hermes_sha() -> None:
    (
        AdmissionEvidenceState,
        RuntimeAdmissionError,
        RuntimeAdmissionPlanner,
        RuntimeComponent,
    ) = _runtime_admission_contract()

    planner = RuntimeAdmissionPlanner()
    plan = planner.build(
        accepted_hermes_sha="hermes-sha-1",
        observed_hermes_sha="hermes-sha-1",
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
    )

    assert plan.hermes_sha == "hermes-sha-1"
    assert plan.runtime_state is AdmissionEvidenceState.NOT_RUN
    assert plan.execute is False
    assert plan.profiles_to_admit == ("factory-orchestrator",)
    assert plan.skills_to_admit == ("factory-reading-project-truth",)
    assert tuple(component.value for component in plan.components) == (
        "FACTORY_PACKAGE",
        "PROFILE_DISTRIBUTIONS",
        "FACTORY_SKILLS",
        "KANBAN_HIGH_ASSURANCE_POLICY",
        "NATIVE_PROFILE_CRON",
        "DASHBOARD_PLUGIN",
        "GATEWAY_HITL_ADAPTER",
        "NORTHBOUND_CONTROL_INTEGRATION",
    )
    assert RuntimeComponent.DASHBOARD_PLUGIN in plan.components

    with pytest.raises(RuntimeAdmissionError, match="exact Hermes SHA"):
        planner.build(
            accepted_hermes_sha="hermes-sha-1",
            observed_hermes_sha="hermes-sha-2",
            profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
            skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        )


@pytest.mark.parametrize("state_name", ["FAIL", "NOT_RUN", "UNKNOWN", "STALE", "ABSENT"])
def test_runtime_admission_fails_closed_on_non_pass_profile_eval(state_name: str) -> None:
    (
        AdmissionEvidenceState,
        RuntimeAdmissionError,
        RuntimeAdmissionPlanner,
        _,
    ) = _runtime_admission_contract()
    state = AdmissionEvidenceState[state_name]

    with pytest.raises(RuntimeAdmissionError, match="Profile evaluation must PASS"):
        RuntimeAdmissionPlanner().build(
            accepted_hermes_sha="hermes-sha-1",
            observed_hermes_sha="hermes-sha-1",
            profile_eval_states={"factory-orchestrator": state},
            skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        )


@pytest.mark.parametrize("state_name", ["FAIL", "NOT_RUN", "UNKNOWN", "STALE", "ABSENT"])
def test_runtime_admission_fails_closed_on_non_pass_skill_eval(state_name: str) -> None:
    (
        AdmissionEvidenceState,
        RuntimeAdmissionError,
        RuntimeAdmissionPlanner,
        _,
    ) = _runtime_admission_contract()
    state = AdmissionEvidenceState[state_name]

    with pytest.raises(RuntimeAdmissionError, match="Skill evaluation must PASS"):
        RuntimeAdmissionPlanner().build(
            accepted_hermes_sha="hermes-sha-1",
            observed_hermes_sha="hermes-sha-1",
            profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
            skill_eval_states={"factory-reading-project-truth": state},
        )
