from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


@dataclass(frozen=True)
class SkillBehavioralEvalCase:
    candidate_kind: str
    candidate_id: str
    gate: str
    prompt: str
    toolsets: tuple[str, ...]
    expected_response: str
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
        if not self.expected_response.strip():
            raise ValueError("Skill behavioral eval expected_response is required")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 900:
            raise ValueError("Skill behavioral eval timeout must be between 1 and 900 seconds")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.candidate_kind, self.candidate_id, self.gate)


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

            argv: list[str] = [
                self._hermes_executable,
                "-z",
                case.prompt,
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

            state = (
                SkillEvalState.PASS
                if response == case.expected_response.strip()
                else SkillEvalState.FAIL
            )
            return SkillEvalEvidence(
                skill_id=item.candidate_id,
                source_digest=item.candidate_digest,
                gate=item.check,
                state=state,
                evidence_ref=self._evidence_ref(item, case, response),
                evaluator=self._EVALUATOR,
            )

    @staticmethod
    def _evidence_ref(
        item: EvalWorkItem,
        case: SkillBehavioralEvalCase,
        response: str,
    ) -> str:
        payload = json.dumps(
            {
                "candidate_kind": item.candidate_kind,
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "gate": item.check,
                "case": {
                    "prompt": case.prompt,
                    "toolsets": list(case.toolsets),
                    "expected_response": case.expected_response,
                },
                "observed_response": response,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return f"hermes-skill-eval:sha256:{hashlib.sha256(payload).hexdigest()}"
