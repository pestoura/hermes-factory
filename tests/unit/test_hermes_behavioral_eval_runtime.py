from __future__ import annotations

from pathlib import Path

import pytest

from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.governance.hermes_behavioral_eval_runtime import (
    BehavioralEvalCase,
    BehavioralEvalRuntimeError,
    EvalCommandResult,
    HermesBehavioralEvalRuntime,
)
from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.agents import ProfileEvalState


class FakeRunner:
    def __init__(self, results: list[EvalCommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str], int]] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> EvalCommandResult:
        self.calls.append((argv, cwd, dict(env), timeout_seconds))
        if not self.results:
            raise AssertionError("unexpected command")
        return self.results.pop(0)


def _profile(tmp_path: Path) -> Path:
    root = tmp_path / "profile"
    root.mkdir()
    (root / "distribution.yaml").write_text(
        "name: factory-software-engineer\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (root / "SOUL.md").write_text("# Factory Software Engineer\n", encoding="utf-8")
    return root


def _item(profile: Path, *, check: str = "routing_correctness") -> EvalWorkItem:
    return EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        candidate_digest=digest_artifact(profile),
        check=check,
        requires_independent_reviewer=check == "independent_review",
    )


def _case(*, expected: str = "IMPLEMENT") -> BehavioralEvalCase:
    return BehavioralEvalCase(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        check="routing_correctness",
        prompt="Select the single approved routing outcome.",
        toolsets=("vision",),
        skills=(),
        expected_response=expected,
        timeout_seconds=90,
    )


def test_profile_eval_installs_candidate_into_isolated_home_and_runs_exact_oneshot(tmp_path):
    profile = _profile(tmp_path)
    runner = FakeRunner(
        [
            EvalCommandResult(returncode=0, stdout="installed\n", stderr=""),
            EvalCommandResult(returncode=0, stdout="IMPLEMENT\n", stderr=""),
        ]
    )
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={
            ("PROFILE", "factory-software-engineer", "routing_correctness"): _case()
        },
        model="eval-model",
        base_environment={"PROVIDER_RUNTIME_INPUT": "present"},
    )

    evidence = runtime.evaluate(_item(profile))

    assert evidence.state is ProfileEvalState.PASS
    assert evidence.profile_id == "factory-software-engineer"
    assert evidence.dimension == "routing_correctness"
    assert evidence.evaluator == "factory-hermes-behavioral-eval-runtime"
    assert evidence.evidence_ref.startswith("hermes-eval:sha256:")

    install_argv, install_cwd, install_env, install_timeout = runner.calls[0]
    assert install_argv == (
        "hermes",
        "profile",
        "install",
        str(profile),
        "--name",
        "factory-software-engineer",
        "-y",
    )
    assert install_cwd != profile
    assert install_timeout == 90
    assert install_env["HOME"] != str(Path.home())
    assert install_env["HERMES_HOME"].startswith(install_env["HOME"])
    assert install_env["PROVIDER_RUNTIME_INPUT"] == "present"

    run_argv, run_cwd, run_env, run_timeout = runner.calls[1]
    assert run_argv == (
        "hermes",
        "-p",
        "factory-software-engineer",
        "-z",
        "Select the single approved routing outcome.",
        "--model",
        "eval-model",
        "--toolsets",
        "vision",
    )
    assert run_cwd == install_cwd
    assert run_env == install_env
    assert run_timeout == 90


def test_response_mismatch_is_behavioral_fail_not_runtime_error(tmp_path):
    profile = _profile(tmp_path)
    runner = FakeRunner(
        [
            EvalCommandResult(0, "installed\n", ""),
            EvalCommandResult(0, "REVIEW\n", ""),
        ]
    )
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={("PROFILE", "factory-software-engineer", "routing_correctness"): _case()},
        model="eval-model",
        base_environment={},
    )

    evidence = runtime.evaluate(_item(profile))

    assert evidence.state is ProfileEvalState.FAIL
    assert evidence.evidence_ref.startswith("hermes-eval:sha256:")


def test_runtime_failure_never_becomes_candidate_fail_or_pass(tmp_path):
    profile = _profile(tmp_path)
    runner = FakeRunner([EvalCommandResult(2, "", "install failed")])
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={("PROFILE", "factory-software-engineer", "routing_correctness"): _case()},
        model="eval-model",
        base_environment={},
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="profile install"):
        runtime.evaluate(_item(profile))


def test_independent_review_is_never_automated(tmp_path):
    profile = _profile(tmp_path)
    runner = FakeRunner([])
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={},
        model="eval-model",
        base_environment={},
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="independent review"):
        runtime.evaluate(_item(profile, check="independent_review"))

    assert runner.calls == []


def test_digest_drift_fails_before_any_hermes_command(tmp_path):
    profile = _profile(tmp_path)
    item = _item(profile)
    (profile / "SOUL.md").write_text("drift\n", encoding="utf-8")
    runner = FakeRunner([])
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={("PROFILE", "factory-software-engineer", "routing_correctness"): _case()},
        model="eval-model",
        base_environment={},
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="digest drift"):
        runtime.evaluate(item)

    assert runner.calls == []


def test_case_requires_explicit_nonempty_toolset_allowlist():
    with pytest.raises(ValueError, match="toolset"):
        BehavioralEvalCase(
            candidate_kind="PROFILE",
            candidate_id="factory-software-engineer",
            check="routing_correctness",
            prompt="route",
            toolsets=(),
            skills=(),
            expected_response="IMPLEMENT",
            timeout_seconds=90,
        )


def test_missing_case_and_skill_work_items_fail_closed(tmp_path):
    profile = _profile(tmp_path)
    runtime = HermesBehavioralEvalRuntime(
        runner=FakeRunner([]),
        profile_artifacts={"factory-software-engineer": profile},
        cases={},
        model="eval-model",
        base_environment={},
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="case"):
        runtime.evaluate(_item(profile))

    skill_item = EvalWorkItem(
        candidate_kind="SKILL",
        candidate_id="factory-example",
        candidate_digest="a" * 64,
        check="skill_green",
        requires_independent_reviewer=False,
    )
    with pytest.raises(BehavioralEvalRuntimeError, match="SKILL"):
        runtime.evaluate(skill_item)
