from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import yaml

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_execution import EvalWorkItem
from hermes_factory.skills.artifacts import compile_skill_artifact
from hermes_factory.skills.evals import SkillEvalEvidence, SkillEvalState


class SkillEvalRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvalCommandResult:
    returncode: int
    stdout: str
    stderr: str


class EvalCommandRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> EvalCommandResult: ...


class SubprocessEvalCommandRunner:
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> EvalCommandResult:
        try:
            completed = subprocess.run(
                list(argv),
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return EvalCommandResult(
                returncode=124,
                stdout=stdout,
                stderr=stderr or "command timed out",
            )
        return EvalCommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


_AUTOMATABLE_SKILL_GATES = frozenset(
    {"baseline_red", "skill_green", "variation_eval", "pressure_eval"}
)
_SKILL_CASE_SCHEMA = "hermes.factory/skill-behavioral-cases/v1.2"
_SKILL_SCENARIO_NAMES = frozenset({"core", "variation", "pressure"})
_SKILL_GATE_SCENARIOS = {
    "baseline_red": "core",
    "skill_green": "core",
    "variation_eval": "variation",
    "pressure_eval": "pressure",
}


@dataclass(frozen=True)
class SkillBehavioralEvalCase:
    candidate_kind: str
    candidate_id: str
    gate: str
    prompt: str
    toolsets: tuple[str, ...]
    expected_response: str
    canonical_labels: tuple[str, ...]
    timeout_seconds: int = 90

    def __post_init__(self) -> None:
        if self.candidate_kind != "SKILL":
            raise ValueError("Skill behavioral eval case requires candidate_kind=SKILL")
        if not self.candidate_id.strip():
            raise ValueError("Skill behavioral eval candidate_id is required")
        if self.gate not in _AUTOMATABLE_SKILL_GATES:
            raise ValueError(f"Skill behavioral eval gate is not automatable: {self.gate}")
        if not self.prompt.strip():
            raise ValueError("Skill behavioral eval prompt is required")
        if not self.toolsets or any(not value.strip() for value in self.toolsets):
            raise ValueError("Skill behavioral eval requires an explicit toolset allowlist")
        expected = self.expected_response.strip()
        if not expected:
            raise ValueError("Skill behavioral eval expected_response is required")
        if "\n" in expected or len(expected) > 64:
            raise ValueError(
                "Skill behavioral eval expected_response must be a short single-line value"
            )
        labels = tuple(label.strip() for label in self.canonical_labels)
        if not labels or any(not label or "\n" in label or len(label) > 64 for label in labels):
            raise ValueError("Skill behavioral eval canonical_labels must be short single-line values")
        if len(set(labels)) != len(labels):
            raise ValueError("Skill behavioral eval canonical_labels must be unique")
        if expected not in labels:
            raise ValueError("Skill behavioral eval expected_response must be in canonical_labels")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 900:
            raise ValueError("Skill behavioral eval timeout must be between 1 and 900 seconds")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.candidate_kind, self.candidate_id, self.gate)


def _require_mapping(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SkillEvalRuntimeError(f"{label} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise SkillEvalRuntimeError(f"{label} keys must be strings")
    return cast(dict[str, Any], value)


def _load_yaml_mapping(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SkillEvalRuntimeError(f"{label} must be a regular file")
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SkillEvalRuntimeError(f"{label} could not be loaded") from exc
    return _require_mapping(document, label=label)


def _skill_case_entry(
    skill_id: str,
    scenario_name: str,
    value: object,
) -> tuple[str, str]:
    entry = _require_mapping(
        value,
        label=f"Skill {skill_id} {scenario_name} case",
    )
    if set(entry) != {"scenario", "expected_response"}:
        raise SkillEvalRuntimeError(
            f"Skill {skill_id} {scenario_name} case must contain scenario and expected_response"
        )
    scenario = entry["scenario"]
    expected = entry["expected_response"]
    if not isinstance(scenario, str) or not scenario.strip():
        raise SkillEvalRuntimeError(
            f"Skill {skill_id} {scenario_name} scenario must be non-empty text"
        )
    if not isinstance(expected, str) or not expected.strip():
        raise SkillEvalRuntimeError(
            f"Skill {skill_id} {scenario_name} expected_response must be non-empty text"
        )
    expected = expected.strip()
    if "\n" in expected or len(expected) > 64:
        raise SkillEvalRuntimeError(
            f"Skill {skill_id} {scenario_name} expected_response must be a short single-line value"
        )
    return scenario.strip(), expected


def _skill_eval_prompt(scenario: str) -> str:
    return (
        "Evaluate one bounded Hermes Software Factory Skill scenario. "
        f"Scenario: {scenario} "
        "Apply the candidate Skill method when it is available in the current Hermes context. "
        "Do not invent missing evidence, authority, approvals, runtime state, requirements, or exceptions. "
        "Keep the decision bounded to the supplied scenario. "
        "If the candidate Skill is unavailable, do not guess its canonical label. "
        "When the candidate Skill is available, return the shortest exact canonical classification/action label "
        "that appears verbatim in the method and best matches the scenario; do not return surrounding prose, paraphrases, or synonyms. "
        "Reply with exactly one token or short phrase representing the method's required "
        "classification/action, and nothing else."
    )


def load_skill_behavioral_case_registry(
    registry_path: Path,
    *,
    skill_sources: Mapping[str, Path],
) -> dict[tuple[str, str, str], SkillBehavioralEvalCase]:
    document = _load_yaml_mapping(
        registry_path,
        label="Skill behavioral case registry",
    )
    if document.get("schema") != _SKILL_CASE_SCHEMA:
        raise SkillEvalRuntimeError("unsupported Skill behavioral case registry schema")
    skills = _require_mapping(
        document.get("skills"),
        label="Skill behavioral case registry skills",
    )

    expected_skill_ids = set(skill_sources)
    observed_skill_ids = set(skills)
    if observed_skill_ids != expected_skill_ids:
        missing = sorted(expected_skill_ids - observed_skill_ids)
        extra = sorted(observed_skill_ids - expected_skill_ids)
        raise SkillEvalRuntimeError(
            f"Skill set mismatch: missing={missing!r} extra={extra!r}"
        )

    cases: dict[tuple[str, str, str], SkillBehavioralEvalCase] = {}
    for skill_id in sorted(expected_skill_ids):
        source = Path(skill_sources[skill_id])
        if source.is_symlink() or not source.is_dir():
            raise SkillEvalRuntimeError(f"Skill source must be a regular directory: {skill_id}")
        raw_skill_cases = _require_mapping(
            skills[skill_id],
            label=f"Skill {skill_id} cases",
        )
        if set(raw_skill_cases) != _SKILL_SCENARIO_NAMES:
            raise SkillEvalRuntimeError(
                f"Skill {skill_id} case set mismatch: "
                f"expected={sorted(_SKILL_SCENARIO_NAMES)!r} "
                f"observed={sorted(raw_skill_cases)!r}"
            )

        scenario_cases = {
            scenario_name: _skill_case_entry(
                skill_id,
                scenario_name,
                raw_skill_cases[scenario_name],
            )
            for scenario_name in sorted(_SKILL_SCENARIO_NAMES)
        }
        canonical_labels = tuple(
            dict.fromkeys(
                scenario_cases[name][1]
                for name in ("core", "variation", "pressure")
            )
        )
        for gate, scenario_name in _SKILL_GATE_SCENARIOS.items():
            scenario, expected_response = scenario_cases[scenario_name]
            prompt = _skill_eval_prompt(scenario)
            if expected_response in prompt:
                raise SkillEvalRuntimeError(
                    f"Skill {skill_id} {scenario_name} case leaks expected_response in prompt"
                )
            case = SkillBehavioralEvalCase(
                candidate_kind="SKILL",
                candidate_id=skill_id,
                gate=gate,
                prompt=prompt,
                toolsets=("vision",),
                expected_response=expected_response,
                canonical_labels=canonical_labels,
                timeout_seconds=90,
            )
            if case.key in cases:
                raise SkillEvalRuntimeError(f"duplicate Skill behavioral eval case: {case.key!r}")
            cases[case.key] = case

    return cases


class HermesSkillEvalRuntime:
    """Evaluate Factory Skills in a disposable native Hermes sandbox.

    ``baseline_red`` deliberately runs without materializing or selecting the
    candidate Skill. The remaining automated gates compile the exact canonical
    Skill into an isolated ``HERMES_HOME`` and select it explicitly through the
    native ``--skills`` mechanism. Independent review is never automated here.
    """

    _EVALUATOR = "factory-hermes-skill-eval-runtime"

    def __init__(
        self,
        *,
        runner: EvalCommandRunner,
        skill_sources: Mapping[str, Path],
        cases: Mapping[tuple[str, str, str], SkillBehavioralEvalCase],
        model: str,
        base_environment: Mapping[str, str],
        hermes_executable: str = "hermes",
    ) -> None:
        if not model.strip():
            raise ValueError("Skill behavioral eval model is required")
        if not hermes_executable.strip():
            raise ValueError("Hermes executable is required")
        self._runner = runner
        self._skill_sources = {
            skill_id: Path(path) for skill_id, path in skill_sources.items()
        }
        self._cases = dict(cases)
        self._model = model
        self._base_environment = dict(base_environment)
        self._hermes_executable = hermes_executable

        for key, case in self._cases.items():
            if key != case.key:
                raise ValueError(f"Skill behavioral eval case key mismatch: {key!r}")

    def evaluate(self, item: EvalWorkItem) -> SkillEvalEvidence:
        if item.requires_independent_reviewer or item.check == "independent_review":
            raise SkillEvalRuntimeError(
                "independent review cannot be automated by the Hermes Skill eval runtime"
            )
        if item.candidate_kind != "SKILL":
            raise SkillEvalRuntimeError(
                f"{item.candidate_kind} evaluation is not supported by the Skill runtime"
            )
        if item.check not in _AUTOMATABLE_SKILL_GATES:
            raise SkillEvalRuntimeError(
                f"Skill evaluation gate is not automatable: {item.check}"
            )

        case = self._cases.get((item.candidate_kind, item.candidate_id, item.check))
        if case is None:
            raise SkillEvalRuntimeError(
                f"no Skill behavioral eval case for {item.candidate_id} {item.check}"
            )

        source = self._skill_sources.get(item.candidate_id)
        if source is None:
            raise SkillEvalRuntimeError(
                f"Skill source is unavailable for {item.candidate_id}"
            )
        if source.is_symlink() or not source.is_dir():
            raise SkillEvalRuntimeError(
                f"Skill source must be a regular directory: {item.candidate_id}"
            )
        observed_digest = digest_artifact(source)
        if observed_digest != item.candidate_digest:
            raise SkillEvalRuntimeError(
                "Skill candidate digest drift: "
                f"expected={item.candidate_digest} observed={observed_digest}"
            )

        with tempfile.TemporaryDirectory(
            prefix="hermes-factory-skill-eval-"
        ) as temporary:
            sandbox = Path(temporary).resolve()
            home = sandbox / "home"
            hermes_home = home / ".hermes"
            workspace = sandbox / "workspace"
            home.mkdir()
            hermes_home.mkdir()
            workspace.mkdir()

            environment = dict(self._base_environment)
            environment["HOME"] = str(home)
            environment["HERMES_HOME"] = str(hermes_home)

            use_skill = item.check != "baseline_red"
            if use_skill:
                compile_skill_artifact(
                    source,
                    canonical_id=item.candidate_id,
                    destination_root=hermes_home / "skills",
                )

            runtime_prompt = case.prompt
            if use_skill:
                label_set = json.dumps(list(case.canonical_labels), ensure_ascii=False)
                runtime_prompt += (
                    f" Candidate method canonical labels: {label_set}. "
                    "Select exactly one label from this set and return it verbatim; "
                    "do not add surrounding prose, qualifiers, prefixes, suffixes, or synonyms."
                )

            argv: list[str] = [
                self._hermes_executable,
                "-z",
                runtime_prompt,
                "--model",
                self._model,
                "--toolsets",
                ",".join(case.toolsets),
            ]
            if use_skill:
                argv.extend(("--skills", item.candidate_id))

            result = self._runner.run(
                tuple(argv),
                cwd=workspace,
                env=environment,
                timeout_seconds=case.timeout_seconds,
            )
            if result.returncode != 0:
                raise SkillEvalRuntimeError(
                    "Hermes oneshot failed in Skill eval sandbox: "
                    f"exit={result.returncode}"
                )
            response = result.stdout.strip()
            if not response:
                raise SkillEvalRuntimeError(
                    "Hermes oneshot produced no Skill behavioral evaluation response"
                )

            matches_target = response == case.expected_response.strip()
            if item.check == "baseline_red":
                state = SkillEvalState.FAIL if matches_target else SkillEvalState.PASS
            else:
                state = SkillEvalState.PASS if matches_target else SkillEvalState.FAIL
            return SkillEvalEvidence(
                skill_id=item.candidate_id,
                source_digest=item.candidate_digest,
                gate=item.check,
                state=state,
                evidence_ref=self._evidence_ref(item, case, runtime_prompt, response),
                evaluator=self._EVALUATOR,
            )

    @staticmethod
    def _evidence_ref(
        item: EvalWorkItem,
        case: SkillBehavioralEvalCase,
        runtime_prompt: str,
        response: str,
    ) -> str:
        payload = json.dumps(
            {
                "candidate_kind": item.candidate_kind,
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "gate": item.check,
                "case": {
                    "prompt": runtime_prompt,
                    "toolsets": list(case.toolsets),
                    "expected_response": case.expected_response,
                    "canonical_labels": list(case.canonical_labels),
                },
                "observed_response": response,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return f"hermes-skill-eval:sha256:{hashlib.sha256(payload).hexdigest()}"
