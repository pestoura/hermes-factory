from hermes_factory.agents import (
    ProfileAdmissionError,
    ProfileEvalEvidence,
    ProfileEvalHarness,
    ProfileEvalRecord,
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


def test_profile_evaluation_api_is_exposed() -> None:
    assert ProfileAdmissionError is not None
    assert ProfileEvalEvidence is not None
    assert ProfileEvalHarness is not None
    assert ProfileEvalRecord is not None
    assert ProfileEvalState is not None


def _passing_evidence(profile_id: str, digest: str, dimensions: tuple[str, ...]):
    return tuple(
        ProfileEvalEvidence(
            profile_id=profile_id,
            profile_digest=digest,
            dimension=dimension,
            state=ProfileEvalState.PASS,
            evidence_ref=f"EV-{dimension}",
            evaluator=(
                "factory-fail-closed-inspector"
                if dimension == "independent_review"
                else "factory-evidence-auditor"
            ),
        )
        for dimension in dimensions
    )


def _error_message(operation) -> str:
    try:
        operation()
    except ProfileAdmissionError as error:
        return str(error)
    raise AssertionError("expected ProfileAdmissionError")


def test_profile_activation_eligibility_requires_every_base_dimension_pass() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-software-engineer"
    digest = "a" * 64

    complete = harness.evaluate(
        profile_id,
        digest,
        _passing_evidence(profile_id, digest, BASE_DIMENSIONS),
        scheduled_duties=False,
    )
    missing_review = harness.evaluate(
        profile_id,
        digest,
        _passing_evidence(profile_id, digest, BASE_DIMENSIONS[:-1]),
        scheduled_duties=False,
    )

    assert complete.eligible_for_activation is True
    assert all(state is ProfileEvalState.PASS for state in complete.required_states.values())
    assert missing_review.eligible_for_activation is False
    assert missing_review.required_states["independent_review"] is ProfileEvalState.NOT_RUN


def test_profile_evidence_must_match_exact_profile_and_digest() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-code-reviewer"
    digest = "b" * 64

    wrong_profile = _passing_evidence("factory-software-engineer", digest, BASE_DIMENSIONS)
    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            wrong_profile,
            scheduled_duties=False,
        )
    )
    assert "another Profile" in message

    stale = list(_passing_evidence(profile_id, digest, BASE_DIMENSIONS))
    stale[0] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest="c" * 64,
        dimension="routing_correctness",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-stale",
        evaluator="factory-evidence-auditor",
    )
    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            tuple(stale),
            scheduled_duties=False,
        )
    )
    assert "digest" in message


def test_profile_evaluation_rejects_duplicate_unknown_and_missing_provenance() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-security-reviewer"
    digest = "d" * 64
    base = list(_passing_evidence(profile_id, digest, BASE_DIMENSIONS))

    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            tuple(base + [base[0]]),
            scheduled_duties=False,
        )
    )
    assert "duplicate" in message

    unknown = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="self_certification",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-unknown",
        evaluator="factory-evidence-auditor",
    )
    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            tuple(base + [unknown]),
            scheduled_duties=False,
        )
    )
    assert "unknown Profile evaluation dimension" in message

    missing_provenance = list(base)
    missing_provenance[0] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="routing_correctness",
        state=ProfileEvalState.PASS,
        evidence_ref="",
        evaluator="factory-evidence-auditor",
    )
    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            tuple(missing_provenance),
            scheduled_duties=False,
        )
    )
    assert "provenance" in message


def test_profile_independent_review_cannot_be_self_review() -> None:
    harness = ProfileEvalHarness()
    profile_id = "factory-release-manager"
    digest = "e" * 64
    evidence = list(_passing_evidence(profile_id, digest, BASE_DIMENSIONS))
    evidence[-1] = ProfileEvalEvidence(
        profile_id=profile_id,
        profile_digest=digest,
        dimension="independent_review",
        state=ProfileEvalState.PASS,
        evidence_ref="EV-self-review",
        evaluator=profile_id,
    )

    message = _error_message(
        lambda: harness.evaluate(
            profile_id,
            digest,
            tuple(evidence),
            scheduled_duties=False,
        )
    )
    assert "independent review" in message
