from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.governance.static_profile_bundle import build_static_profile_eval_bundle
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState

ROOT = Path(__file__).resolve().parents[2]


class PassRuntime:
    def __init__(self) -> None:
        self.items: list[EvalWorkItem] = []

    def evaluate(self, item: EvalWorkItem):
        self.items.append(item)
        if item.requires_independent_reviewer:
            raise AssertionError("independent review must never reach automated runtime")
        if item.candidate_kind == "PROFILE":
            return ProfileEvalEvidence(
                profile_id=item.candidate_id,
                profile_digest=item.candidate_digest,
                dimension=item.check,
                state=ProfileEvalState.PASS,
                evidence_ref=f"test-profile:{item.candidate_id}:{item.check}",
                evaluator="test-automated-profile-runtime",
            )
        if item.candidate_kind == "SKILL":
            return SkillEvalEvidence(
                skill_id=item.candidate_id,
                source_digest=item.candidate_digest,
                gate=item.check,
                state=SkillEvalState.PASS,
                evidence_ref=f"test-skill:{item.candidate_id}:{item.check}",
                evaluator="test-automated-skill-runtime",
            )
        raise AssertionError(f"unexpected candidate kind: {item.candidate_kind}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_load_handoff_rejects_candidate_or_plan_digest_drift(tmp_path: Path) -> None:
    from hermes_factory.governance.automated_eval_bundle import (
        AutomatedEvalBundleError,
        load_behavioral_eval_handoff,
    )

    source = tmp_path / "handoff.json"
    source.write_text(
        json.dumps(
            {
                "schema": "hermes.factory/behavioral-eval-handoff/v1",
                "candidate_sha": "a" * 40,
                "static_evidence_ref": "ci:test:static",
                "work_item_count": 0,
                "profile_work_item_count": 0,
                "skill_work_item_count": 0,
                "independent_review_count": 0,
                "plan_digest": "0" * 64,
                "plan": {
                    "schema": "hermes.factory/eval-execution-plan/v1",
                    "items": [],
                    "blockers": [],
                    "execution_state": "PASS",
                    "execute": False,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AutomatedEvalBundleError, match="candidate"):
        load_behavioral_eval_handoff(source, expected_candidate_sha="b" * 40)

    with pytest.raises(AutomatedEvalBundleError, match="digest"):
        load_behavioral_eval_handoff(source, expected_candidate_sha="a" * 40)


def test_automated_bundle_executes_only_machine_work_and_preserves_source_db(
    tmp_path: Path,
) -> None:
    from hermes_factory.governance.automated_eval_bundle import (
        build_automated_behavioral_eval_bundle,
    )

    candidate_sha = "c" * 40
    static_dir = tmp_path / "static"
    build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=static_dir,
        candidate_sha=candidate_sha,
    )
    source_db = static_dir / "static-profile-evals.db"
    source_digest_before = _sha256(source_db)
    runtime = PassRuntime()

    bundle = build_automated_behavioral_eval_bundle(
        repo_root=ROOT,
        static_bundle_dir=static_dir,
        output_dir=tmp_path / "automated",
        candidate_sha=candidate_sha,
        model="test-model",
        base_environment={},
        runtime=runtime,
        verify_repo_head=False,
    )

    assert len(runtime.items) == 201
    assert sum(item.candidate_kind == "PROFILE" for item in runtime.items) == 85
    assert sum(item.candidate_kind == "SKILL" for item in runtime.items) == 116
    assert not any(item.requires_independent_reviewer for item in runtime.items)
    assert source_digest_before == _sha256(source_db)

    assert bundle.execution_report.attempted_count == 201
    assert bundle.execution_report.recorded_count == 201
    assert bundle.execution_report.passed_count == 201
    assert bundle.execution_report.failed_count == 0
    assert bundle.execution_report.state == "PASS"
    assert bundle.independent_review_count == 46
    assert bundle.residual_plan.execution_state == "NOT_RUN"
    assert len(bundle.residual_plan.items) == 46
    assert all(item.requires_independent_reviewer for item in bundle.residual_plan.items)
    assert bundle.state == "AUTOMATED_PASS_REVIEW_REQUIRED"
    assert bundle.registry_path.is_file()
    assert bundle.report_path.is_file()
    assert bundle.residual_plan_path.is_file()

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    assert report["schema"] == "hermes.factory/automated-behavioral-eval-bundle/v1"
    assert report["candidate_sha"] == candidate_sha
    assert report["automated_item_count"] == 201
    assert report["independent_review_count"] == 46
    assert report["state"] == "AUTOMATED_PASS_REVIEW_REQUIRED"


def test_automated_bundle_refuses_repo_head_mismatch_before_execution(
    tmp_path: Path,
) -> None:
    from hermes_factory.governance.automated_eval_bundle import (
        AutomatedEvalBundleError,
        build_automated_behavioral_eval_bundle,
    )

    candidate_sha = "d" * 40
    static_dir = tmp_path / "static"
    build_static_profile_eval_bundle(
        repo_root=ROOT,
        output_dir=static_dir,
        candidate_sha=candidate_sha,
    )
    runtime = PassRuntime()

    with pytest.raises(AutomatedEvalBundleError, match="repository HEAD"):
        build_automated_behavioral_eval_bundle(
            repo_root=ROOT,
            static_bundle_dir=static_dir,
            output_dir=tmp_path / "automated",
            candidate_sha=candidate_sha,
            model="test-model",
            base_environment={},
            runtime=runtime,
            verify_repo_head=True,
        )

    assert runtime.items == []
