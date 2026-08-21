from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_evidence import EvalEvidenceStore
from hermes_factory.governance.eval_execution import EvalExecutionPlan, EvalWorkItem
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState
from hermes_factory.traceability.registry import SemanticRegistry

PROFILE_ID = "factory-code-reviewer"
SKILL_ID = "factory-tdd-red"
PROFILE_DIGEST = "sha256:" + "a" * 64
SKILL_DIGEST = "sha256:" + "b" * 64
CANDIDATE_SHA = "c" * 40
PROFILE_AUTOMATED = (
    "routing_correctness",
    "refusal_authority_boundary",
    "tool_policy_projection",
    "skill_allowlist",
    "separation_of_duties",
    "handoff_evidence_quality",
    "escalation_correctness",
    "no_internal_mcp_dependency",
)
SKILL_AUTOMATED = (
    "baseline_red",
    "skill_green",
    "variation_eval",
    "pressure_eval",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan() -> EvalExecutionPlan:
    return EvalExecutionPlan(
        items=(
            EvalWorkItem(
                candidate_kind="PROFILE",
                candidate_id=PROFILE_ID,
                candidate_digest=PROFILE_DIGEST,
                check="independent_review",
                requires_independent_reviewer=True,
            ),
            EvalWorkItem(
                candidate_kind="SKILL",
                candidate_id=SKILL_ID,
                candidate_digest=SKILL_DIGEST,
                check="independent_review",
                requires_independent_reviewer=True,
            ),
        ),
        blockers=(),
        execution_state="NOT_RUN",
        execute=False,
    )


def _registry(path: Path, *, fail_profile: bool = False) -> Path:
    store = EvalEvidenceStore(SemanticRegistry(path))
    for dimension in PROFILE_AUTOMATED:
        store.record_profile(
            ProfileEvalEvidence(
                profile_id=PROFILE_ID,
                profile_digest=PROFILE_DIGEST,
                dimension=dimension,
                state=(
                    ProfileEvalState.FAIL
                    if fail_profile and dimension == "routing_correctness"
                    else ProfileEvalState.PASS
                ),
                evidence_ref=f"test-profile:{dimension}",
                evaluator="automated-profile-evaluator",
            )
        )
    for gate in SKILL_AUTOMATED:
        store.record_skill(
            SkillEvalEvidence(
                skill_id=SKILL_ID,
                source_digest=SKILL_DIGEST,
                gate=gate,
                state=SkillEvalState.PASS,
                evidence_ref=f"test-skill:{gate}",
                evaluator="automated-skill-evaluator",
            )
        )
    return path


def test_prepare_review_bundle_requires_only_independent_work_and_passed_prior_gates(
    tmp_path: Path,
) -> None:
    from hermes_factory.governance.independent_review_bundle import (
        prepare_independent_review_bundle,
    )

    registry = _registry(tmp_path / "evals.db")
    packet_path = tmp_path / "review-packet.json"

    packet = prepare_independent_review_bundle(
        registry_path=registry,
        residual_plan=_plan(),
        output_path=packet_path,
        candidate_sha=CANDIDATE_SHA,
    )

    assert packet_path.is_file()
    assert packet.item_count == 2
    assert packet.packet_digest.startswith("sha256:")
    document = json.loads(packet_path.read_text(encoding="utf-8"))
    assert document["schema"] == "hermes.factory/independent-review-packet/v1"
    assert document["candidate_sha"] == CANDIDATE_SHA
    assert document["item_count"] == 2
    assert document["packet_digest"] == packet.packet_digest
    assert [item["candidate_kind"] for item in document["items"]] == ["PROFILE", "SKILL"]
    assert len(document["items"][0]["prior_evidence"]) == len(PROFILE_AUTOMATED)
    assert len(document["items"][1]["prior_evidence"]) == len(SKILL_AUTOMATED)
    assert all(
        evidence["state"] == "PASS"
        for item in document["items"]
        for evidence in item["prior_evidence"]
    )


def test_prepare_review_bundle_refuses_failed_prior_evidence(tmp_path: Path) -> None:
    from hermes_factory.governance.independent_review_bundle import (
        IndependentReviewBundleError,
        prepare_independent_review_bundle,
    )

    registry = _registry(tmp_path / "evals.db", fail_profile=True)

    with pytest.raises(IndependentReviewBundleError, match="prior evidence"):
        prepare_independent_review_bundle(
            registry_path=registry,
            residual_plan=_plan(),
            output_path=tmp_path / "review-packet.json",
            candidate_sha=CANDIDATE_SHA,
        )


def test_prepare_review_bundle_refuses_non_independent_item(tmp_path: Path) -> None:
    from hermes_factory.governance.independent_review_bundle import (
        IndependentReviewBundleError,
        prepare_independent_review_bundle,
    )

    registry = _registry(tmp_path / "evals.db")
    bad_plan = EvalExecutionPlan(
        items=(
            EvalWorkItem(
                candidate_kind="PROFILE",
                candidate_id=PROFILE_ID,
                candidate_digest=PROFILE_DIGEST,
                check="routing_correctness",
                requires_independent_reviewer=False,
            ),
        ),
        blockers=(),
        execution_state="NOT_RUN",
        execute=False,
    )

    with pytest.raises(IndependentReviewBundleError, match="only independent"):
        prepare_independent_review_bundle(
            registry_path=registry,
            residual_plan=bad_plan,
            output_path=tmp_path / "review-packet.json",
            candidate_sha=CANDIDATE_SHA,
        )


def test_import_review_decisions_is_exact_packet_bound_and_source_immutable(
    tmp_path: Path,
) -> None:
    from hermes_factory.governance.independent_review_bundle import (
        import_independent_review_decisions,
        prepare_independent_review_bundle,
    )

    registry = _registry(tmp_path / "evals.db")
    source_digest = _sha256(registry)
    packet_path = tmp_path / "review-packet.json"
    packet = prepare_independent_review_bundle(
        registry_path=registry,
        residual_plan=_plan(),
        output_path=packet_path,
        candidate_sha=CANDIDATE_SHA,
    )
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "schema": "hermes.factory/independent-review-decisions/v1",
                "candidate_sha": CANDIDATE_SHA,
                "packet_digest": packet.packet_digest,
                "reviewer_id": "independent-reviewer-01",
                "decisions": [
                    {
                        "candidate_kind": "PROFILE",
                        "candidate_id": PROFILE_ID,
                        "candidate_digest": PROFILE_DIGEST,
                        "state": "PASS",
                        "evidence_ref": "review:profile:001",
                        "rationale": "Authority and separation boundaries independently reviewed.",
                    },
                    {
                        "candidate_kind": "SKILL",
                        "candidate_id": SKILL_ID,
                        "candidate_digest": SKILL_DIGEST,
                        "state": "PASS",
                        "evidence_ref": "review:skill:001",
                        "rationale": "Skill method and pressure behavior independently reviewed.",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_independent_review_decisions(
        registry_path=registry,
        packet_path=packet_path,
        decisions_path=decisions_path,
        output_registry_path=tmp_path / "reviewed.db",
    )

    assert _sha256(registry) == source_digest
    assert result.output_registry_path.is_file()
    assert result.recorded_count == 2
    assert result.passed_count == 2
    assert result.failed_count == 0
    assert result.state == "PASS"

    store = EvalEvidenceStore(SemanticRegistry(result.output_registry_path))
    profile = store.profile_record(PROFILE_ID, PROFILE_DIGEST, scheduled_duties=False)
    skill = store.skill_gate_states(SKILL_ID, SKILL_DIGEST)
    assert profile.required_states["independent_review"] is ProfileEvalState.PASS
    assert skill["independent_review"] is SkillEvalState.PASS


def test_import_review_decisions_rejects_stale_packet_and_self_review_without_output(
    tmp_path: Path,
) -> None:
    from hermes_factory.governance.independent_review_bundle import (
        IndependentReviewBundleError,
        import_independent_review_decisions,
        prepare_independent_review_bundle,
    )

    registry = _registry(tmp_path / "evals.db")
    packet_path = tmp_path / "review-packet.json"
    packet = prepare_independent_review_bundle(
        registry_path=registry,
        residual_plan=_plan(),
        output_path=packet_path,
        candidate_sha=CANDIDATE_SHA,
    )
    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "schema": "hermes.factory/independent-review-decisions/v1",
                "candidate_sha": CANDIDATE_SHA,
                "packet_digest": "sha256:" + "0" * 64,
                "reviewer_id": PROFILE_ID,
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "reviewed.db"

    with pytest.raises(IndependentReviewBundleError, match="packet digest"):
        import_independent_review_decisions(
            registry_path=registry,
            packet_path=packet_path,
            decisions_path=decisions_path,
            output_registry_path=output,
        )
    assert not output.exists()

    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    decisions["packet_digest"] = packet.packet_digest
    decisions["decisions"] = [
        {
            "candidate_kind": "PROFILE",
            "candidate_id": PROFILE_ID,
            "candidate_digest": PROFILE_DIGEST,
            "state": "PASS",
            "evidence_ref": "review:self",
            "rationale": "invalid self review",
        },
        {
            "candidate_kind": "SKILL",
            "candidate_id": SKILL_ID,
            "candidate_digest": SKILL_DIGEST,
            "state": "PASS",
            "evidence_ref": "review:skill",
            "rationale": "reviewed",
        },
    ]
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")

    with pytest.raises(IndependentReviewBundleError, match="self-review"):
        import_independent_review_decisions(
            registry_path=registry,
            packet_path=packet_path,
            decisions_path=decisions_path,
            output_registry_path=output,
        )
    assert not output.exists()
