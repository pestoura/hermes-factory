from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.governance.hermes_behavioral_eval_runtime import (
    BehavioralEvalCase,
    BehavioralEvalRuntimeError,
    EvalCommandResult,
    HermesBehavioralEvalRuntime,
    SubprocessEvalCommandRunner,
)


class RecordingRunner:
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
    (root / "SOUL.md").write_text("# candidate\n", encoding="utf-8")
    return root


def _item(profile: Path) -> EvalWorkItem:
    return EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        candidate_digest=digest_artifact(profile),
        check="routing_correctness",
        requires_independent_reviewer=False,
    )


def _case() -> BehavioralEvalCase:
    return BehavioralEvalCase(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        check="routing_correctness",
        prompt="Return IMPLEMENT only.",
        toolsets=("vision",),
        skills=(),
        expected_response="IMPLEMENT",
        timeout_seconds=90,
    )


def _runtime(
    profile: Path,
    runner: RecordingRunner,
    *,
    base_environment: dict[str, str] | None = None,
) -> HermesBehavioralEvalRuntime:
    case = _case()
    return HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": profile},
        cases={case.key: case},
        model="eval-model",
        base_environment=base_environment or {},
    )


def test_oneshot_nonzero_exit_is_runtime_error_not_behavioral_fail(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runner = RecordingRunner(
        [
            EvalCommandResult(0, "installed\n", ""),
            EvalCommandResult(7, "", "provider failure"),
        ]
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="oneshot failed"):
        _runtime(profile, runner).evaluate(_item(profile))


def test_empty_oneshot_output_is_runtime_error(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runner = RecordingRunner(
        [
            EvalCommandResult(0, "installed\n", ""),
            EvalCommandResult(0, "  \n", ""),
        ]
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="no behavioral evaluation response"):
        _runtime(profile, runner).evaluate(_item(profile))


def test_subprocess_runner_maps_timeout_to_explicit_124(tmp_path: Path) -> None:
    result = SubprocessEvalCommandRunner().run(
        (sys.executable, "-c", "import time; time.sleep(2)"),
        cwd=tmp_path,
        env={},
        timeout_seconds=1,
    )

    assert result.returncode == 124
    assert "timed out" in result.stderr


def test_sandbox_is_destroyed_after_success(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runner = RecordingRunner(
        [
            EvalCommandResult(0, "installed\n", ""),
            EvalCommandResult(0, "IMPLEMENT\n", ""),
        ]
    )

    _runtime(profile, runner).evaluate(_item(profile))

    sandbox_workspace = runner.calls[0][1]
    assert not sandbox_workspace.exists()
    assert not sandbox_workspace.parent.exists()


def test_sandbox_is_destroyed_after_runtime_failure(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runner = RecordingRunner([EvalCommandResult(3, "", "install failed")])

    with pytest.raises(BehavioralEvalRuntimeError):
        _runtime(profile, runner).evaluate(_item(profile))

    sandbox_workspace = runner.calls[0][1]
    assert not sandbox_workspace.exists()
    assert not sandbox_workspace.parent.exists()


def test_base_environment_cannot_preserve_production_home_paths(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runner = RecordingRunner(
        [
            EvalCommandResult(0, "installed\n", ""),
            EvalCommandResult(0, "IMPLEMENT\n", ""),
        ]
    )
    runtime = _runtime(
        profile,
        runner,
        base_environment={
            "HOME": "/production/home",
            "HERMES_HOME": "/production/hermes",
            "PROVIDER_RUNTIME_INPUT": "opaque-runtime-input",
        },
    )

    runtime.evaluate(_item(profile))

    for _, _, environment, _ in runner.calls:
        assert environment["HOME"] != "/production/home"
        assert environment["HERMES_HOME"] != "/production/hermes"
        assert environment["HERMES_HOME"].startswith(environment["HOME"])
        assert environment["PROVIDER_RUNTIME_INPUT"] == "opaque-runtime-input"


def test_runtime_environment_does_not_change_evidence_identity(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    item = _item(profile)

    first = _runtime(
        profile,
        RecordingRunner(
            [
                EvalCommandResult(0, "installed\n", ""),
                EvalCommandResult(0, "IMPLEMENT\n", ""),
            ]
        ),
        base_environment={"PROVIDER_RUNTIME_INPUT": "secret-A"},
    ).evaluate(item)
    second = _runtime(
        profile,
        RecordingRunner(
            [
                EvalCommandResult(0, "installed\n", ""),
                EvalCommandResult(0, "IMPLEMENT\n", ""),
            ]
        ),
        base_environment={"PROVIDER_RUNTIME_INPUT": "secret-B"},
    ).evaluate(item)

    assert first.evidence_ref == second.evidence_ref


def test_case_mapping_key_mismatch_is_rejected_before_execution(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    case = _case()

    with pytest.raises(ValueError, match="case key mismatch"):
        HermesBehavioralEvalRuntime(
            runner=RecordingRunner([]),
            profile_artifacts={"factory-software-engineer": profile},
            cases={("PROFILE", "factory-software-engineer", "wrong-check"): case},
            model="eval-model",
            base_environment={},
        )


def test_symlinked_profile_candidate_is_rejected_before_execution(tmp_path: Path) -> None:
    real_profile = _profile(tmp_path)
    symlink = tmp_path / "profile-link"
    symlink.symlink_to(real_profile, target_is_directory=True)
    item = EvalWorkItem(
        candidate_kind="PROFILE",
        candidate_id="factory-software-engineer",
        candidate_digest=digest_artifact(real_profile),
        check="routing_correctness",
        requires_independent_reviewer=False,
    )
    runner = RecordingRunner([])
    case = _case()
    runtime = HermesBehavioralEvalRuntime(
        runner=runner,
        profile_artifacts={"factory-software-engineer": symlink},
        cases={case.key: case},
        model="eval-model",
        base_environment={},
    )

    with pytest.raises(BehavioralEvalRuntimeError, match="regular directory"):
        runtime.evaluate(item)

    assert runner.calls == []
