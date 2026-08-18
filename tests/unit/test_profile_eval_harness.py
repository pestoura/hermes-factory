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
