from __future__ import annotations

from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.governance.hermes_skill_eval_runtime import (
    EvalCommandResult,
    HermesSkillEvalRuntime,
    SkillBehavioralEvalCase,
    SkillEvalRuntimeError,
)
from hermes_factory.skills.evals import SkillEvalState

SKILL_ID = "factory-reading-project-truth"


class RecordingRunner:
    def __init__(self, results: list[EvalCommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str], int]] = []
        self.skill_present_during_call: list[bool] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> EvalCommandResult:
        self.calls.append((argv, cwd, dict(env), timeout_seconds))
        skill_path = Path(env["HERMES_HOME"]) / "skills" / SKILL_ID / "SKILL.md"
        self.skill_present_during_call.append(skill_path.is_file())
        if not self.results:
            raise AssertionError("unexpected command")
        return self.results.pop(0)


def _skill(tmp_path: Path) -> Path:
    root = tmp_path / "reading-project-truth"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\n"
        "name: reading-project-truth\n"
        "description: Resolve authoritative sources before technical claims.\n"
        "version: 0.1.0\n"
        "---\n\n"
        "# Reading Project Truth\n\n"
        "Use authoritative sources and never manufacture missing state.\n",
        encoding="utf-8",
    )
    return root


def _case(gate: str, expected_response: str) -> SkillBehavioralEvalCase:
    return SkillBehavioralEvalCase(
        candidate_kind="SKILL",
        candidate_id=SKILL_ID,
        gate=gate,
        prompt="Evaluate the bounded scenario and return one exact token.",
        toolsets=("vision",),
        expected_response=expected_response,
        timeout_seconds=90,
    )


def _item(skill: Path, gate: str, *, independent: bool = False) -> EvalWorkItem:
    return EvalWorkItem(
        candidate_kind="SKILL",
        candidate_id=SKILL_ID,
        candidate_digest=digest_artifact(skill),
        check=gate,
        requires_independent_reviewer=independent,
    )


def _runtime(
    skill: Path,
    runner: RecordingRunner,
    case: SkillBehavioralEvalCase,
) -> HermesSkillEvalRuntime:
    return HermesSkillEvalRuntime(
        runner=runner,
        skill_sources={SKILL_ID: skill},
        cases={case.key: case},
        model="eval-model",
        base_environment={"PROVIDER_RUNTIME_INPUT": "opaque"},
    )


def test_baseline_red_passes_only_when_unskilled_response_misses_target(
    tmp_path: Path,
) -> None:
    skill = _skill(tmp_path)
    case = _case("baseline_red", "BLOCKED")
    runner = RecordingRunner([EvalCommandResult(0, "TAKE\n", "")])

    evidence = _runtime(skill, runner, case).evaluate(_item(skill, "baseline_red"))

    assert evidence.state is SkillEvalState.PASS
    assert evidence.gate == "baseline_red"
    assert runner.skill_present_during_call == [False]
    assert "--skills" not in runner.calls[0][0]
    assert not Path(runner.calls[0][2]["HERMES_HOME"]).exists()


def test_baseline_red_fails_when_unskilled_response_already_matches_target(
    tmp_path: Path,
) -> None:
    skill = _skill(tmp_path)
    case = _case("baseline_red", "BLOCKED")
    runner = RecordingRunner([EvalCommandResult(0, "BLOCKED\n", "")])

    evidence = _runtime(skill, runner, case).evaluate(_item(skill, "baseline_red"))

    assert evidence.state is SkillEvalState.FAIL


def test_skill_green_compiles_and_selects_exact_canonical_skill(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    case = _case("skill_green", "TAKE")
    runner = RecordingRunner([EvalCommandResult(0, "TAKE\n", "")])

    evidence = _runtime(skill, runner, case).evaluate(_item(skill, "skill_green"))

    assert evidence.state is SkillEvalState.PASS
    assert evidence.source_digest == digest_artifact(skill)
    assert runner.skill_present_during_call == [True]
    argv = runner.calls[0][0]
    assert argv[argv.index("--skills") + 1] == SKILL_ID
    assert not Path(runner.calls[0][2]["HERMES_HOME"]).exists()


def test_variation_or_pressure_response_mismatch_is_behavioral_fail(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    case = _case("pressure_eval", "REFUSE")
    runner = RecordingRunner([EvalCommandResult(0, "TAKE\n", "")])

    evidence = _runtime(skill, runner, case).evaluate(_item(skill, "pressure_eval"))

    assert evidence.state is SkillEvalState.FAIL
    assert evidence.gate == "pressure_eval"


def test_independent_review_is_never_automated(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    case = _case("skill_green", "TAKE")
    runner = RecordingRunner([])

    with pytest.raises(SkillEvalRuntimeError, match="independent review"):
        _runtime(skill, runner, case).evaluate(
            _item(skill, "independent_review", independent=True)
        )

    assert runner.calls == []


def test_source_digest_drift_blocks_before_execution(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    case = _case("variation_eval", "TAKE")
    runner = RecordingRunner([])
    item = EvalWorkItem(
        candidate_kind="SKILL",
        candidate_id=SKILL_ID,
        candidate_digest="0" * 64,
        check="variation_eval",
        requires_independent_reviewer=False,
    )

    with pytest.raises(SkillEvalRuntimeError, match="digest drift"):
        _runtime(skill, runner, case).evaluate(item)

    assert runner.calls == []


def test_command_failure_is_runtime_error_not_behavioral_fail(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    case = _case("skill_green", "TAKE")
    runner = RecordingRunner([EvalCommandResult(7, "", "provider failure")])

    with pytest.raises(SkillEvalRuntimeError, match="oneshot failed"):
        _runtime(skill, runner, case).evaluate(_item(skill, "skill_green"))
