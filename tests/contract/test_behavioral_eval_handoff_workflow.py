from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/factory-ci.yml"


def test_static_eval_artifact_also_uploads_behavioral_eval_handoff():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "artifacts/static-profile-evals/behavioral-eval-plan.json" in text
    assert "if-no-files-found: error" in text
