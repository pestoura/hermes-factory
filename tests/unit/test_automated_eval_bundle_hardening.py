from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.governance.static_profile_bundle import build_static_profile_eval_bundle

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExplodingRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, item: EvalWorkItem):
        self.calls += 1
        raise RuntimeError(f"synthetic runtime failure for {item.candidate_id}")


def test_automated_bundle_rejects_symlinked_static_bundle(tmp_path: Path) -> None:
    from hermes_factory.governance.automated_eval_bundle import (
        AutomatedEvalBundleError,
        build_automated_behavioral_eval_bundle,
    )

    candidate_sha = "e" * 40
    real_static = tmp_path / "real-static"
    build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=real_static,
        candidate_sha=candidate_sha,
    )
    linked_static = tmp_path / "linked-static"
    linked_static.symlink_to(real_static, target_is_directory=True)

    with pytest.raises(AutomatedEvalBundleError, match="regular directory"):
        build_automated_behavioral_eval_bundle(
            repo_root=ROOT,
            static_bundle_dir=linked_static,
            output_dir=tmp_path / "automated",
            candidate_sha=candidate_sha,
            model="test-model",
            base_environment={},
            runtime=ExplodingRuntime(),
            verify_repo_head=False,
        )

    assert not (tmp_path / "automated").exists()


def test_runtime_error_leaves_no_partial_canonical_output(tmp_path: Path) -> None:
    from hermes_factory.governance.automated_eval_bundle import (
        build_automated_behavioral_eval_bundle,
    )

    candidate_sha = "f" * 40
    static_dir = tmp_path / "static"
    build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=static_dir,
        candidate_sha=candidate_sha,
    )
    source_db = static_dir / "static-profile-evals.db"
    source_digest = _sha256(source_db)
    output_dir = tmp_path / "automated"
    runtime = ExplodingRuntime()

    with pytest.raises(RuntimeError, match="synthetic runtime failure"):
        build_automated_behavioral_eval_bundle(
            repo_root=ROOT,
            static_bundle_dir=static_dir,
            output_dir=output_dir,
            candidate_sha=candidate_sha,
            model="test-model",
            base_environment={},
            runtime=runtime,
            verify_repo_head=False,
        )

    assert runtime.calls == 1
    assert _sha256(source_db) == source_digest
    assert not output_dir.exists()
    assert not list(tmp_path.glob(".automated-evals-*"))
