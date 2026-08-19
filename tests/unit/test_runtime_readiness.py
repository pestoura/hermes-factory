from hermes_factory.runtime.admission import AdmissionEvidenceState


def _readiness_contract():
    try:
        from hermes_factory.runtime.readiness import RuntimeReadinessAssessor
    except ModuleNotFoundError as exc:
        raise AssertionError("Phase P runtime readiness assessor is not implemented") from exc
    return RuntimeReadinessAssessor


def test_runtime_readiness_requires_complete_pass_evidence() -> None:
    assessor = _readiness_contract()()

    assessment = assessor.assess(
        required_profile_ids=("factory-orchestrator", "factory-software-engineer"),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={
            "factory-orchestrator": AdmissionEvidenceState.PASS,
            "factory-software-engineer": AdmissionEvidenceState.PASS,
        },
        skill_eval_states={
            "factory-reading-project-truth": AdmissionEvidenceState.PASS,
        },
    )

    assert assessment.ready is True
    assert assessment.blockers == ()
    assert assessment.to_manifest()["ready"] is True
    assert len(assessment.digest) == 64


def test_runtime_readiness_marks_missing_evidence_absent_and_blocks() -> None:
    assessor = _readiness_contract()()

    assessment = assessor.assess(
        required_profile_ids=("factory-orchestrator", "factory-software-engineer"),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={
            "factory-orchestrator": AdmissionEvidenceState.PASS,
        },
        skill_eval_states={
            "factory-reading-project-truth": AdmissionEvidenceState.PASS,
        },
    )

    assert assessment.ready is False
    assert assessment.profile_states["factory-software-engineer"] is AdmissionEvidenceState.ABSENT
    assert "Profile factory-software-engineer=ABSENT" in assessment.blockers


def test_runtime_readiness_preserves_non_pass_state_and_never_promotes_it() -> None:
    assessor = _readiness_contract()()

    assessment = assessor.assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={
            "factory-orchestrator": AdmissionEvidenceState.PASS,
        },
        skill_eval_states={
            "factory-reading-project-truth": AdmissionEvidenceState.NOT_RUN,
        },
    )

    assert assessment.ready is False
    assert assessment.skill_states["factory-reading-project-truth"] is AdmissionEvidenceState.NOT_RUN
    assert "Skill factory-reading-project-truth=NOT_RUN" in assessment.blockers


def test_runtime_readiness_manifest_is_deterministic() -> None:
    assessor = _readiness_contract()()

    first = assessor.assess(
        required_profile_ids=("b", "a"),
        required_skill_ids=("y", "x"),
        profile_eval_states={"a": AdmissionEvidenceState.PASS, "b": AdmissionEvidenceState.PASS},
        skill_eval_states={"x": AdmissionEvidenceState.PASS, "y": AdmissionEvidenceState.PASS},
    )
    second = assessor.assess(
        required_profile_ids=("a", "b"),
        required_skill_ids=("x", "y"),
        profile_eval_states={"b": AdmissionEvidenceState.PASS, "a": AdmissionEvidenceState.PASS},
        skill_eval_states={"y": AdmissionEvidenceState.PASS, "x": AdmissionEvidenceState.PASS},
    )

    assert first.to_manifest() == second.to_manifest()
    assert first.digest == second.digest


def test_runtime_readiness_blocks_unexpected_evidence_identities() -> None:
    assessor = _readiness_contract()()

    assessment = assessor.assess(
        required_profile_ids=("factory-orchestrator",),
        required_skill_ids=("factory-reading-project-truth",),
        profile_eval_states={
            "factory-orchestrator": AdmissionEvidenceState.PASS,
            "factory-unknown-profile": AdmissionEvidenceState.PASS,
        },
        skill_eval_states={
            "factory-reading-project-truth": AdmissionEvidenceState.PASS,
            "factory-unknown-skill": AdmissionEvidenceState.PASS,
        },
    )

    assert assessment.ready is False
    assert "Unexpected Profile evidence factory-unknown-profile=PASS" in assessment.blockers
    assert "Unexpected Skill evidence factory-unknown-skill=PASS" in assessment.blockers
