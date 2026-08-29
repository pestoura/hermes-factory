import json
from pathlib import Path

from hermes_factory.traceability.registry import SemanticRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_static_profile_eval_bundle_persists_exact_head_ci_evidence(tmp_path):
    from hermes_factory.governance.static_profile_bundle import (
        build_static_profile_eval_bundle,
    )

    candidate_sha = "a" * 40
    bundle = build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=tmp_path / "evidence",
        candidate_sha=candidate_sha,
    )

    assert bundle.report.candidate_count == 17
    assert bundle.report.evidence_count == 68
    assert bundle.report.passed_count == 68
    assert bundle.report.failed_count == 0
    assert bundle.report.state == "PASS"
    assert bundle.remaining_work_items == 247
    assert bundle.manifest_path.exists()
    assert bundle.registry_path.exists()

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "hermes.factory/static-profile-eval-bundle/v1"
    assert manifest["candidate_sha"] == candidate_sha
    assert manifest["evidence_ref"] == f"ci:{candidate_sha}:static-profile-evals"
    assert manifest["report"]["evidence_count"] == 68
    assert manifest["remaining_work_items"] == 247
    assert len(manifest["profiles"]) == 17
    assert {
        state
        for profile in manifest["profiles"].values()
        for state in profile["states"].values()
    } == {"PASS"}

    registry = SemanticRegistry(bundle.registry_path)
    evidence = registry.list_evidence()
    assert len(evidence) == 68
    assert {item["state"] for item in evidence} == {"PASS"}
    assert all(item["candidate"].startswith("profile:") for item in evidence)
