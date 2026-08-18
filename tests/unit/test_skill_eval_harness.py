import pytest

from hermes_factory.skills.evals import (
    SkillEvalEvidence,
    SkillEvalHarness,
    SkillEvalState,
)
from hermes_factory.skills.system import SkillAdmissionError

GATES = (
    "baseline_red",
    "skill_green",
    "variation_eval",
    "pressure_eval",
    "independent_review",
)


def _evidence(
    gate: str,
    *,
    digest: str = "sha256:abc",
    state: SkillEvalState = SkillEvalState.PASS,
):
    return SkillEvalEvidence(
        skill_id="factory-reading-project-truth",
        source_digest=digest,
        gate=gate,
        state=state,
        evidence_ref=f"evidence:{gate}",
        evaluator="factory-evidence-auditor",
    )


def test_missing_not_run_or_failed_gate_never_promotes():
    harness = SkillEvalHarness()

    missing = harness.evaluate(
        "factory-reading-project-truth",
        "sha256:abc",
        tuple(_evidence(g) for g in GATES[:-1]),
    )
    not_run = harness.evaluate(
        "factory-reading-project-truth",
        "sha256:abc",
        tuple(
            _evidence(
                g,
                state=(
                    SkillEvalState.NOT_RUN
                    if g == "pressure_eval"
                    else SkillEvalState.PASS
                ),
            )
            for g in GATES
        ),
    )
    failed = harness.evaluate(
        "factory-reading-project-truth",
        "sha256:abc",
        tuple(
            _evidence(
                g,
                state=(
                    SkillEvalState.FAIL
                    if g == "variation_eval"
                    else SkillEvalState.PASS
                ),
            )
            for g in GATES
        ),
    )

    assert missing.promotable is False
    assert not_run.promotable is False
    assert failed.promotable is False


def test_all_five_pass_for_exact_source_digest_is_promotable():
    result = SkillEvalHarness().evaluate(
        "factory-reading-project-truth",
        "sha256:abc",
        tuple(_evidence(g) for g in GATES),
    )

    assert result.promotable is True
    assert result.require_active("factory-reading-project-truth").lifecycle == "ACTIVE"


def test_stale_digest_cannot_be_reused_for_changed_skill():
    with pytest.raises(SkillAdmissionError, match="source digest"):
        SkillEvalHarness().evaluate(
            "factory-reading-project-truth",
            "sha256:new",
            tuple(_evidence(g, digest="sha256:old") for g in GATES),
        )


def test_duplicate_gate_evidence_fails_closed_instead_of_last_write_wins():
    records = tuple(_evidence(g) for g in GATES) + (_evidence("pressure_eval"),)

    with pytest.raises(SkillAdmissionError, match="duplicate"):
        SkillEvalHarness().evaluate(
            "factory-reading-project-truth",
            "sha256:abc",
            records,
        )
