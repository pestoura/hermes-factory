from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/factory-ci.yml"


def test_static_profile_eval_job_uses_exact_pr_head_and_uploads_durable_bundle():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "static-profile-evals:" in text
    assert "needs: test" in text
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert "python -m hermes_factory.governance.static_profile_bundle" in text
    assert "--candidate-sha \"$FACTORY_CANDIDATE_SHA\"" in text
    assert "actions/upload-artifact@v4" in text
    assert "artifacts/static-profile-evals/static-profile-evals.json" in text
    assert "artifacts/static-profile-evals/static-profile-evals.db" in text
