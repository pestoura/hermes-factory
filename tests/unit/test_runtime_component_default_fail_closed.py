from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.readiness import RuntimeReadinessAssessor


def test_runtime_readiness_omitted_component_evidence_is_absent_and_blocked() -> None:
    assessment = RuntimeReadinessAssessor().assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
    )

    assert assessment.ready is False
    assert set(assessment.component_states) == set(RuntimeComponent)
    assert all(
        state is AdmissionEvidenceState.ABSENT
        for state in assessment.component_states.values()
    )
    assert "Component NORTHBOUND_CONTROL_INTEGRATION=ABSENT" in assessment.blockers
