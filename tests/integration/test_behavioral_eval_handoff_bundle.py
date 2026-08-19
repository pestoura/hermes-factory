import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_static_bundle_materializes_digest_bound_behavioral_eval_handoff(tmp_path):
    from hermes_factory.governance.static_profile_bundle import (
        build_static_profile_eval_bundle,
    )

    candidate_sha = "b" * 40
    bundle = build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=tmp_path / "evidence",
        candidate_sha=candidate_sha,
    )

    assert bundle.behavioral_plan_path.exists()
    payload = json.loads(bundle.behavioral_plan_path.read_text(encoding="utf-8"))

    assert payload["schema"] == "hermes.factory/behavioral-eval-handoff/v1"
    assert payload["candidate_sha"] == candidate_sha
    assert payload["static_evidence_ref"] == f"ci:{candidate_sha}:static-profile-evals"
    assert payload["work_item_count"] == 247
    assert payload["profile_work_item_count"] == 102
    assert payload["skill_work_item_count"] == 145
    assert payload["independent_review_count"] == 46
    assert payload["plan"]["execution_state"] == "NOT_RUN"
    assert payload["plan"]["blockers"] == []
    assert payload["plan"]["execute"] is False
    assert len(payload["plan"]["items"]) == 247

    profile_checks = {
        item["check"]
        for item in payload["plan"]["items"]
        if item["candidate_kind"] == "PROFILE"
    }
    assert profile_checks == {
        "routing_correctness",
        "refusal_authority_boundary",
        "separation_of_duties",
        "handoff_evidence_quality",
        "escalation_correctness",
        "independent_review",
    }
