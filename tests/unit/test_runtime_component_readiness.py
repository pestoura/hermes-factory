from hermes_factory.runtime.admission import (
    AdmissionEvidenceState,
    RuntimeComponent,
)
from hermes_factory.runtime.readiness import RuntimeReadinessAssessor


def _passing_components() -> dict[RuntimeComponent, AdmissionEvidenceState]:
    return {component: AdmissionEvidenceState.PASS for component in RuntimeComponent}


def test_runtime_readiness_requires_all_runtime_components_pass() -> None:
    assessment = RuntimeReadinessAssessor().assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=_passing_components(),
    )

    assert assessment.ready is True
    assert assessment.blockers == ()
    assert set(assessment.component_states) == set(RuntimeComponent)
    assert assessment.to_manifest()["component_states"] == {
        component.value: "PASS" for component in RuntimeComponent
    }


def test_runtime_readiness_blocks_on_external_component_blocker() -> None:
    components = _passing_components()
    components[RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION] = AdmissionEvidenceState.BLOCKED

    assessment = RuntimeReadinessAssessor().assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=components,
    )

    assert assessment.ready is False
    assert (
        assessment.component_states[RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION]
        is AdmissionEvidenceState.BLOCKED
    )
    assert "Component NORTHBOUND_CONTROL_INTEGRATION=BLOCKED" in assessment.blockers


def test_runtime_readiness_marks_missing_component_evidence_absent() -> None:
    components = _passing_components()
    del components[RuntimeComponent.DASHBOARD_PLUGIN]

    assessment = RuntimeReadinessAssessor().assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={"factory-orchestrator": AdmissionEvidenceState.PASS},
        skill_eval_states={"factory-reading-project-truth": AdmissionEvidenceState.PASS},
        component_states=components,
    )

    assert assessment.ready is False
    assert (
        assessment.component_states[RuntimeComponent.DASHBOARD_PLUGIN]
        is AdmissionEvidenceState.ABSENT
    )
    assert "Component DASHBOARD_PLUGIN=ABSENT" in assessment.blockers
