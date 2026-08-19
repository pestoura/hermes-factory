from pathlib import Path

WORKFLOW = Path(".github/workflows/factory-ci.yml")


def test_factory_ci_builds_and_uploads_exact_head_package_candidate():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "factory-package-candidate:" in text
    assert "FACTORY_CANDIDATE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert "python -m pip wheel . --no-deps --wheel-dir artifacts/factory-package" in text
    assert "factory-package.json" in text
    assert "hermes_factory.runtime.package_candidate" in text
    assert "name: factory-package-candidate-${{ env.FACTORY_CANDIDATE_SHA }}" in text
