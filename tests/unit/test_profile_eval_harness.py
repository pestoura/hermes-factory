import pytest

from hermes_factory import agents


BASE_DIMENSIONS = (
    "routing_correctness",
    "refusal_authority_boundary",
    "tool_policy_projection",
    "skill_allowlist",
    "separation_of_duties",
    "handoff_evidence_quality",
    "escalation_correctness",
    "no_internal_mcp_dependency",
    "independent_review",
)


def _api():
    names = (
        "ProfileAdmissionError",
        "ProfileEvalEvidence",
        "ProfileEvalHarness",
        "ProfileEvalState",
    )
    missing = [name for name in names if getattr(agents, name, None) is None]
    assert not missing, f"missing Profile evaluation API: {missing}"
    return (
        agents.ProfileAdmissionError,
        agents.ProfileEvalEvidence,
        agents.ProfileEvalHarness,
        agents.ProfileEvalState,
    )


def _evidence(
    profile_id: str,
    digest: str,
    dimensions: tuple[str, ...] = BASE_DIMENSIONS,
    *,
    state=None,
):
    _, Evidence, _, State = _api()
    selected_state = State.PASS if state is None else state
    records = []
    for dimension in dimensions:
        evaluator = "factory-evidence-auditor"
        if dimension == "independent_review":
            evaluator = "factory-fail-closed-inspector"
        records.append(
            Evidence(
                profile_id=profile_id,
                profile_digest=digest,
                dimension=dimension,
                state=selected_state,
                evidence_ref=f"EV-{dimension}",
                evaluator=evaluator,
            )
        )
    return tuple(records)


def test_profile_is_eligible_only_when_every_required_dimension_passes() -> None:
    _, _, Harness, State = _api()
    harness = Harness()
    profile_id = "factory-software-engineer"
    digest = "a" * 64

    passed = harness.evaluate(
        profile_id,
        digest,
        _evidence(profile_id, digest),
        scheduled_duties=False,
    )
    incomplete = harness.evaluate(
        profile_id,
        digest,
        _evidence(profile_id, digest, BASE_DIMENSIONS[:-1]),
        scheduled_duties=False,
    )

    assert passed.eligible_for_activation is True
    assert all(state is State.PASS for state in passed.required_states.values())
    assert incomplete.eligible_for_activation is False
    assert incomplete.required_states["independent_review"] is State.NOT_RUN


def test_failed_dimension_prevents_activation_eligibility() -> None:
    _, Evidence, Harness, State = _api()
    harness = Harness()
    profile_id = "factory-security-reviewer"
    digest = "b" * 64
    evidence = list(_evidence(profile_id, digest))
    evidence[0] = Evidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="routing_correctness",
        state=State.FAIL,
        evidence_ref="EV-routing-fail",
        evaluator="factory-evidence-auditor",
    )

    record = harness.evaluate(
        profile_id,
        digest,
        tuple(evidence),
        scheduled_duties=False,
    )

    assert record.eligible_for_activation is False
    assert record.required_states["routing_correctness"] is State.FAIL


def test_scheduled_profile_requires_native_cron_projection_evidence() -> None:
    _, _, Harness, State = _api()
    harness = Harness()
    profile_id = "factory-orchestrator"
    digest = "c" * 64

    incomplete = harness.evaluate(
        profile_id,
        digest,
        _evidence(profile_id, digest),
        scheduled_duties=True,
    )
    complete = harness.evaluate(
        profile_id,
        digest,
        _evidence(profile_id, digest, BASE_DIMENSIONS + ("native_cron_projection",)),
        scheduled_duties=True,
    )

    assert incomplete.eligible_for_activation is False
    assert incomplete.required_states["native_cron_projection"] is State.NOT_RUN
    assert complete.eligible_for_activation is True


def test_profile_evidence_is_bound_to_exact_profile_and_digest() -> None:
    Error, Evidence, Harness, State = _api()
    harness = Harness()
    profile_id = "factory-code-reviewer"
    digest = "d" * 64

    with pytest.raises(Error, match="another Profile"):
        harness.evaluate(
            profile_id,
            digest,
            _evidence("factory-software-engineer", digest),
            scheduled_duties=False,
        )

    stale = list(_evidence(profile_id, digest))
    stale[0] = Evidence(
        profile_id=profile_id,
        profile_digest="e" * 64,
        dimension="routing_correctness",
        state=State.PASS,
        evidence_ref="EV-stale",
        evaluator="factory-evidence-auditor",
    )
    with pytest.raises(Error, match="digest"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(stale),
            scheduled_duties=False,
        )


def test_profile_eval_rejects_duplicate_unknown_or_self_review_evidence() -> None:
    Error, Evidence, Harness, State = _api()
    harness = Harness()
    profile_id = "factory-release-manager"
    digest = "f" * 64
    base = list(_evidence(profile_id, digest))

    with pytest.raises(Error, match="duplicate"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(base + [base[0]]),
            scheduled_duties=False,
        )

    unknown = Evidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="self_certification",
        state=State.PASS,
        evidence_ref="EV-unknown",
        evaluator="factory-evidence-auditor",
    )
    with pytest.raises(Error, match="unknown Profile evaluation dimension"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(base + [unknown]),
            scheduled_duties=False,
        )

    self_review = list(base)
    self_review[-1] = Evidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="independent_review",
        state=State.PASS,
        evidence_ref="EV-self-review",
        evaluator=profile_id,
    )
    with pytest.raises(Error, match="independent review"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(self_review),
            scheduled_duties=False,
        )
