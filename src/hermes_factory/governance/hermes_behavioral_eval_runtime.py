from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hermes_factory.agents import ProfileEvalEvidence, ProfileEvalState
from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.governance.eval_execution import EvalWorkItem


class BehavioralEvalRuntimeError(RuntimeError):
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


@dataclass(frozen=True)
class BehavioralEvalCase:
    candidate_kind: str
    candidate_id: str
    check: str
    prompt: str
    toolsets: tuple[str, ...]
    skills: tuple[str, ...]
    expected_response: str
    timeout_seconds: int = 90

    def __post_init__(self) -> None:
        if self.candidate_kind != "PROFILE":
            raise ValueError("behavioral eval case currently supports PROFILE only")
        for label, value in {
            "candidate_id": self.candidate_id,
            "check": self.check,
            "prompt": self.prompt,
            "expected_response": self.expected_response,
        }.items():
            if not value.strip():
                raise ValueError(f"{label} is required")
        if not self.toolsets or any(not value.strip() for value in self.toolsets):
            raise ValueError("behavioral eval case requires an explicit toolset allowlist")
        if any(not value.strip() for value in self.skills):
            raise ValueError("behavioral eval case Skill IDs must be non-empty")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 900:
            raise ValueError("behavioral eval timeout must be between 1 and 900 seconds")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.candidate_kind, self.candidate_id, self.check)


class HermesBehavioralEvalRuntime:
    """Isolated Hermes oneshot runtime for non-independent Profile checks.

    This runtime deliberately does not automate independent review and does not
    yet execute Skill lifecycle gates. Each invocation installs one exact
    Profile candidate into a disposable HOME/HERMES_HOME, runs one explicit
    Hermes oneshot case with an explicit toolset allowlist, returns only a
    digest-bound evidence reference, and then destroys the sandbox.
    """

    _EVALUATOR = "factory-hermes-behavioral-eval-runtime"

    def __init__(
        self,
        *,
        runner: EvalCommandRunner,
        profile_artifacts: Mapping[str, Path],
        cases: Mapping[tuple[str, str, str], BehavioralEvalCase],
        model: str,
        base_environment: Mapping[str, str],
        hermes_executable: str = "hermes",
    ) -> None:
        if not model.strip():
            raise ValueError("behavioral eval model is required")
        if not hermes_executable.strip():
            raise ValueError("Hermes executable is required")
        self._runner = runner
        self._profile_artifacts = {
            profile_id: Path(path) for profile_id, path in profile_artifacts.items()
        }
        self._cases = dict(cases)
        self._model = model
        self._base_environment = dict(base_environment)
        self._hermes_executable = hermes_executable

        for key, case in self._cases.items():
            if key != case.key:
                raise ValueError(f"behavioral eval case key mismatch: {key!r}")

    def evaluate(self, item: EvalWorkItem) -> ProfileEvalEvidence:
        if item.requires_independent_reviewer or item.check == "independent_review":
            raise BehavioralEvalRuntimeError(
                "independent review cannot be automated by the Hermes behavioral runtime"
            )
        if item.candidate_kind != "PROFILE":
            raise BehavioralEvalRuntimeError(
                f"{item.candidate_kind} behavioral evaluation is not implemented by this runtime"
            )

        case = self._cases.get((item.candidate_kind, item.candidate_id, item.check))
        if case is None:
            raise BehavioralEvalRuntimeError(
                f"no behavioral eval case for {item.candidate_kind} "
                f"{item.candidate_id} {item.check}"
            )

        profile = self._profile_artifacts.get(item.candidate_id)
        if profile is None:
            raise BehavioralEvalRuntimeError(
                f"Profile artifact is unavailable for {item.candidate_id}"
            )
        if profile.is_symlink() or not profile.is_dir():
            raise BehavioralEvalRuntimeError(
                f"Profile artifact must be a regular directory: {item.candidate_id}"
            )
        observed_digest = digest_artifact(profile)
        if observed_digest != item.candidate_digest:
            raise BehavioralEvalRuntimeError(
                "Profile candidate digest drift: "
                f"expected={item.candidate_digest} observed={observed_digest}"
            )

        with tempfile.TemporaryDirectory(prefix="hermes-factory-eval-") as temporary:
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

            install = self._runner.run(
                (
                    self._hermes_executable,
                    "profile",
                    "install",
                    str(profile),
                    "--name",
                    item.candidate_id,
                    "-y",
                ),
                cwd=workspace,
                env=environment,
                timeout_seconds=case.timeout_seconds,
            )
            if install.returncode != 0:
                raise BehavioralEvalRuntimeError(
                    "Hermes profile install failed in behavioral eval sandbox: "
                    f"exit={install.returncode}"
                )

            argv: list[str] = [
                self._hermes_executable,
                "-p",
                item.candidate_id,
                "-z",
                case.prompt,
                "--model",
                self._model,
                "--toolsets",
                ",".join(case.toolsets),
            ]
            for skill_id in case.skills:
                argv.extend(("--skills", skill_id))

            result = self._runner.run(
                tuple(argv),
                cwd=workspace,
                env=environment,
                timeout_seconds=case.timeout_seconds,
            )
            if result.returncode != 0:
                raise BehavioralEvalRuntimeError(
                    "Hermes oneshot failed in behavioral eval sandbox: "
                    f"exit={result.returncode}"
                )
            response = result.stdout.strip()
            if not response:
                raise BehavioralEvalRuntimeError(
                    "Hermes oneshot produced no behavioral evaluation response"
                )

            state = (
                ProfileEvalState.PASS
                if response == case.expected_response.strip()
                else ProfileEvalState.FAIL
            )
            return ProfileEvalEvidence(
                profile_id=item.candidate_id,
                profile_digest=item.candidate_digest,
                dimension=item.check,
                state=state,
                evidence_ref=self._evidence_ref(item, case, response),
                evaluator=self._EVALUATOR,
            )

    @staticmethod
    def _evidence_ref(
        item: EvalWorkItem,
        case: BehavioralEvalCase,
        response: str,
    ) -> str:
        payload = json.dumps(
            {
                "candidate_kind": item.candidate_kind,
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "check": item.check,
                "case": {
                    "prompt": case.prompt,
                    "toolsets": list(case.toolsets),
                    "skills": list(case.skills),
                    "expected_response": case.expected_response,
                },
                "observed_response": response,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return f"hermes-eval:sha256:{hashlib.sha256(payload).hexdigest()}"
