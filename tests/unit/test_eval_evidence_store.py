from hermes_factory.agents.evals import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.runtime.admission import AdmissionEvidenceState
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.traceability.registry import SemanticRegistry


def _store(tmp_path):
    return EvalEvidenceStore(SemanticRegistry(tmp_path / "factory.db"))


def test_profile_eval_evidence_is_persisted_and_missing_dimensions_stay_not_run(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_profile(
        ProfileEvalEvidence(
            profile_id="factory-orchestrator",
            profile_digest="profile-digest-a",
            dimension="routing_correctness",
            state=ProfileEvalState.PASS,
            evidence_ref="ci://profile/routing/1",
            evaluator="factory-code-reviewer",
        )
    )

    record = store.profile_record(
        "factory-orchestrator",
        "profile-digest-a",
        scheduled_duties=False,
    )

    assert record.required_states["routing_correctness"] is ProfileEvalState.PASS
    assert record.required_states["independent_review"] is ProfileEvalState.NOT_RUN
    assert record.eligible_for_activation is False
    assert (
        store.profile_admission_state(
            "factory-orchestrator",
            "profile-digest-a",
            scheduled_duties=False,
        )
        is AdmissionEvidenceState.NOT_RUN
    )


def test_profile_eval_evidence_is_never_reused_across_candidate_digest(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_profile(
        ProfileEvalEvidence(
            profile_id="factory-orchestrator",
            profile_digest="profile-digest-a",
            dimension="routing_correctness",
            state=ProfileEvalState.PASS,
            evidence_ref="ci://profile/routing/1",
            evaluator="factory-code-reviewer",
        )
    )

    record = store.profile_record(
        "factory-orchestrator",
        "profile-digest-b",
        scheduled_duties=False,
    )

    assert set(record.required_states.values()) == {ProfileEvalState.NOT_RUN}
    assert (
        store.profile_admission_state(
            "factory-orchestrator",
            "profile-digest-b",
            scheduled_duties=False,
        )
        is AdmissionEvidenceState.NOT_RUN
    )


def test_profile_fail_is_preserved_as_fail_not_not_run(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_profile(
        ProfileEvalEvidence(
            profile_id="factory-orchestrator",
            profile_digest="profile-digest-a",
            dimension="routing_correctness",
            state=ProfileEvalState.FAIL,
            evidence_ref="ci://profile/routing/1",
            evaluator="factory-code-reviewer",
        )
    )

    assert (
        store.profile_admission_state(
            "factory-orchestrator",
            "profile-digest-a",
            scheduled_duties=False,
        )
        is AdmissionEvidenceState.FAIL
    )


def test_skill_eval_evidence_requires_all_five_gates_for_pass(tmp_path) -> None:
    store = _store(tmp_path)
    gates = (
        "baseline_red",
        "skill_green",
        "variation_eval",
        "pressure_eval",
        "independent_review",
    )
    for gate in gates[:-1]:
        store.record_skill(
            SkillEvalEvidence(
                skill_id="factory-reading-project-truth",
                source_digest="skill-digest-a",
                gate=gate,
                state=SkillEvalState.PASS,
                evidence_ref=f"ci://skill/{gate}/1",
                evaluator="factory-integration-tester",
            )
        )

    assert (
        store.skill_admission_state(
            "factory-reading-project-truth",
            "skill-digest-a",
        )
        is AdmissionEvidenceState.NOT_RUN
    )

    store.record_skill(
        SkillEvalEvidence(
            skill_id="factory-reading-project-truth",
            source_digest="skill-digest-a",
            gate="independent_review",
            state=SkillEvalState.PASS,
            evidence_ref="ci://skill/independent-review/1",
            evaluator="factory-code-reviewer",
        )
    )

    assert store.skill_record("factory-reading-project-truth", "skill-digest-a").promotable
    assert (
        store.skill_admission_state(
            "factory-reading-project-truth",
            "skill-digest-a",
        )
        is AdmissionEvidenceState.PASS
    )


def test_skill_fail_is_preserved_and_old_digest_is_not_reused(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_skill(
        SkillEvalEvidence(
            skill_id="factory-reading-project-truth",
            source_digest="skill-digest-a",
            gate="pressure_eval",
            state=SkillEvalState.FAIL,
            evidence_ref="ci://skill/pressure/1",
            evaluator="factory-security-reviewer",
        )
    )

    assert (
        store.skill_admission_state(
            "factory-reading-project-truth",
            "skill-digest-a",
        )
        is AdmissionEvidenceState.FAIL
    )
    assert (
        store.skill_admission_state(
            "factory-reading-project-truth",
            "skill-digest-b",
        )
        is AdmissionEvidenceState.NOT_RUN
    )
