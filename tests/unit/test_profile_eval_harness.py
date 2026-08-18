import pytest

from hermes_factory.agents import (
    ProfileAdmissionError,
    ProfileEvalEvidence,
    ProfileEvalHarness,
    ProfileEvalState,
)


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


def _evidence(
    profile_id: str,
    digest: str,
    dimensions: tuple[str, ...] = BASE_DIMENSIONS,
    *,
    state: ProfileEvalState = ProfileEvalState.PASS,
) -> tuple[ProfileEvalEvidence, ...]:
    records = []
    for dimension in dimensions:
        evaluator = "factory-evidence-auditor"
        if dimension == "independent_review":
            evaluator = "factory-fail-closed-inspector"
        records.append(
            ProfileEvalEvidence(
                profile_id=profile_id,
                profile_digest=digest,
                dimension=dimension,
                state=state,
                evidence_ref=f"EV-{dimension}",
                evaluator=evaluator,
            )
        )
    return tuple(records)


def test_profile_is_eligible_only_when_every_required_dimension_passes() -> None:
    harness = ProfileEvalHarness()
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
    assert all(state is ProfileEvalState.PASS for state in passed.required_states.values())
    assert incomplete.eligible_for_activation is False
    assert incomplete.required_states["independent_review"] is ProfileEvalState.NOT_RUN


def test_failed_dimension_prevents_activation_eligibility() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-security-reviewer"
    digest = "b" * 64
    evidence = list(_evidence(profile_id, digest))
    evidence[0] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="routing_correctness",
        state=ProfileEvalState.FAIL,
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
    assert record.required_states["routing_correctness"] is ProfileEvalState.FAIL


def test_scheduled_profile_requires_native_cron_projection_evidence() -> None:
    harness = ProfileEvalHarness()
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
    assert incomplete.required_states["native_cron_projection"] is ProfileEvalState.NOT_RUN
    assert complete.eligible_for_activation is True


def test_profile_evidence_is_bound_to_exact_profile_and_digest() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-code-reviewer"
    digest = "d" * 64

    with pytest.raises(ProfileAdmissionError, match="another Profile"):
        harness.evaluate(
            profile_id,
            digest,
            _evidence("factory-software-engineer", digest),
            scheduled_duties=False,
        )

    stale = list(_evidence(profile_id, digest))
    stale[0] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest="e" * 64,
        dimension="routing_correctness",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-stale",
        evaluator="factory-evidence-auditor",
    )
    with pytest.raises(ProfileAdmissionError, match="digest"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(stale),
            scheduled_duties=False,
        )


def test_profile_eval_rejects_duplicate_unknown_or_self_review_evidence() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-release-manager"
    digest = "f" * 64
    base = list(_evidence(profile_id, digest))

    with pytest.raises(ProfileAdmissionError, match="duplicate"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(base + [base[0]]),
            scheduled_duties=False,
        )

    unknown = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="self_certification",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-unknown",
        evaluator="factory-evidence-auditor",
    )
    with pytest.raises(ProfileAdmissionError, match="unknown Profile evaluation dimension"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(base + [unknown]),
            scheduled_duties=False,
        )

    self_review = list(base)
    self_review[-1] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="independent_review",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-self-review",
        evaluator=profile_id,
    )
    with pytest.raises(ProfileAdmissionError, match="independent review"):
        harness.evaluate(
            profile_id,
            digest,
            tuple(self_review),
            scheduled_duties=False,
        )
