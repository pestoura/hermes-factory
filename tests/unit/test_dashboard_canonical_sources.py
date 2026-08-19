from pathlib import Path

from hermes_factory.adapters.jds import JDSGatePlanAdapter
from hermes_factory.agents.evals import (
    ProfileEvalEvidence,
    ProfileEvalHarness,
    ProfileEvalState,
)
from hermes_factory.contracts import EngineeringProfileReference
from hermes_factory.dashboard import FactoryDashboardProjection
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalHarness, SkillEvalState
from hermes_factory.traceability import FactorySourceEvidenceRecorder, SemanticRegistry


def _profile() -> EngineeringProfileReference:
    return EngineeringProfileReference(
        api_version="engineering.jarvas/v1",
        kind="ProjectEngineeringProfile",
        standard="JDS-001",
        platform_ref="platform-sha",
        criticality="high",
        digest="f" * 64,
    )


def _jds_plan() -> dict[str, object]:
    return {
        "schema": "engineering.jarvas/gate-plan-v1",
        "standard": "JDS-001",
        "platformRef": "platform-sha",
        "criticality": "high",
        "changeSource": "git-diff",
        "ambiguousImpact": False,
        "effectiveCapabilities": ["python", "repository-security"],
        "selectedCapabilities": ["python", "repository-security"],
        "selectedGates": ["python_quality", "secret_scan"],
        "skippedCapabilities": {"docs": "change-impact-not-triggered"},
    }


def test_dashboard_reads_jds_plan_as_observed_not_executed_gate_state(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    recorder = FactorySourceEvidenceRecorder(registry)
    plan = JDSGatePlanAdapter().consume(_jds_plan(), profile=_profile())

    evidence_id = recorder.record_jds_gate_plan(candidate="sha-1", plan=plan)
    row = registry.get_evidence(evidence_id)

    assert row["kind"] == "JDS_GATE_PLAN"
    assert row["state"] == "OBSERVED"
    assert row["candidate"] == "sha-1"
    assert row["payload"]["selected_gates"] == ["python_quality", "secret_scan"]
    assert row["payload"]["plan_digest"] == plan.plan_digest

    snapshot = FactoryDashboardProjection(registry).snapshot(candidate="sha-1")
    assert snapshot["jds_gates"] == [row]


def test_dashboard_preserves_profile_eval_not_run_and_provenance(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    recorder = FactorySourceEvidenceRecorder(registry)
    profile_id = "factory-software-engineer"
    profile_digest = "a" * 64
    evidence = (
        ProfileEvalEvidence(
            profile_id=profile_id,
            profile_digest=profile_digest,
            dimension="routing_correctness",
            state=ProfileEvalState.PASS,
            evidence_ref="EV-routing",
            evaluator="factory-evidence-auditor",
        ),
    )
    evaluation = ProfileEvalHarness().evaluate(
        profile_id,
        profile_digest,
        evidence,
        scheduled_duties=False,
    )

    evidence_id = recorder.record_profile_evaluation(
        candidate="sha-1",
        evaluation=evaluation,
        evidence=evidence,
    )
    row = registry.get_evidence(evidence_id)

    assert row["kind"] == "PROFILE_EVAL"
    assert row["state"] == "NOT_RUN"
    assert row["payload"]["required_states"]["routing_correctness"] == "PASS"
    assert row["payload"]["required_states"]["independent_review"] == "NOT_RUN"
    assert row["payload"]["provenance"]["routing_correctness"] == {
        "evidence_ref": "EV-routing",
        "evaluator": "factory-evidence-auditor",
    }
    assert "independent_review" not in row["payload"]["provenance"]

    snapshot = FactoryDashboardProjection(registry).snapshot(candidate="sha-1")
    assert snapshot["agent_evals"] == [row]


def test_dashboard_preserves_skill_gate_states_digest_and_provenance(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    recorder = FactorySourceEvidenceRecorder(registry)
    skill_id = "factory-reading-project-truth"
    source_digest = "sha256:source"
    evidence = (
        SkillEvalEvidence(
            skill_id=skill_id,
            source_digest=source_digest,
            gate="baseline_red",
            state=SkillEvalState.PASS,
            evidence_ref="EV-red",
            evaluator="factory-evidence-auditor",
        ),
        SkillEvalEvidence(
            skill_id=skill_id,
            source_digest=source_digest,
            gate="skill_green",
            state=SkillEvalState.FAIL,
            evidence_ref="EV-green-fail",
            evaluator="factory-evidence-auditor",
        ),
    )
    evaluation = SkillEvalHarness().evaluate(skill_id, source_digest, evidence)

    evidence_id = recorder.record_skill_evaluation(
        candidate="sha-1",
        skill_id=skill_id,
        source_digest=source_digest,
        evaluation=evaluation,
        evidence=evidence,
    )
    row = registry.get_evidence(evidence_id)

    assert row["kind"] == "SKILL_EVAL"
    assert row["state"] == "FAIL"
    assert row["payload"]["source_digest"] == source_digest
    assert row["payload"]["gate_states"] == {
        "baseline_red": "PASS",
        "skill_green": "FAIL",
        "variation_eval": "NOT_RUN",
        "pressure_eval": "NOT_RUN",
        "independent_review": "NOT_RUN",
    }
    assert row["payload"]["provenance"]["skill_green"] == {
        "evidence_ref": "EV-green-fail",
        "evaluator": "factory-evidence-auditor",
    }

    registry.record_evidence(
        "profile:other-candidate",
        kind="PROFILE_EVAL",
        state="PASS",
        candidate="sha-2",
        payload={"profile_id": "other"},
    )
    snapshot = FactoryDashboardProjection(registry).snapshot(candidate="sha-1")
    assert snapshot["skill_evals"] == [row]
    assert all(item["candidate"] == "sha-1" for item in snapshot["agent_evals"])
