from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import InstallOperation


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, argv: tuple[str, ...]) -> CommandResult: ...


class SubprocessCommandRunner:
    def run(self, argv: tuple[str, ...]) -> CommandResult:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CREATED_JOB = re.compile(r"^Created job:\s*(\S+)\s*$", re.MULTILINE)
_SUPPORTED_ACTIONS = {
    "INSTALL_NATIVE_PROFILE_DISTRIBUTION",
    "CREATE_NATIVE_PROFILE_CRON_DUTY",
    "APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
}


def _receipt(payload: dict[str, str]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _load_receipt(receipt: str) -> dict[str, object]:
    try:
        payload = json.loads(receipt)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid install rollback receipt") from exc
    if not isinstance(payload, dict):
        raise TypeError("invalid install rollback receipt")
    return payload


class HermesJarvasInstallRuntime:
    """Concrete, fail-closed adapter for proven native Hermes install actions.

    Only operations with verified upstream apply and compensation mechanisms are
    supported. The full Phase P plan therefore remains blocked by preflight
    until every remaining symbolic operation has an equally concrete mapping.
    """

    def __init__(self, *, command_runner: CommandRunner | None = None) -> None:
        self._runner = command_runner or SubprocessCommandRunner()

    @staticmethod
    def _profile_id(operation: InstallOperation) -> str:
        argv = operation.argv
        if len(argv) != 7:
            raise RuntimeError("invalid native Profile install command")
        if argv[:3] != ("hermes", "profile", "install"):
            raise RuntimeError("invalid native Profile install command")
        if argv[4] != "--name" or argv[6] != "-y":
            raise RuntimeError("invalid native Profile install command")
        profile_id = argv[5]
        if not _PROFILE_ID.fullmatch(profile_id):
            raise RuntimeError("invalid native Profile id")
        if "--force" in argv:
            raise RuntimeError("forced Profile overwrite is not supported")
        if operation.source != argv[3]:
            raise RuntimeError("Profile install source does not match command")
        source = Path(argv[3])
        if source.is_symlink() or not source.is_dir():
            raise RuntimeError("Profile install source is not a regular directory")
        if operation.target != f"HERMES_HOME/profiles/{profile_id}":
            raise RuntimeError("Profile install target does not match Profile id")
        return profile_id

    @staticmethod
    def _cron_profile_id(operation: InstallOperation) -> str:
        argv = operation.argv
        if len(argv) < 8:
            raise RuntimeError("invalid native Profile cron command")
        if argv[0] != "hermes" or argv[1] != "-p":
            raise RuntimeError("invalid native Profile cron command")
        profile_id = argv[2]
        if not _PROFILE_ID.fullmatch(profile_id):
            raise RuntimeError("invalid native Profile cron id")
        if argv[3:5] != ("cron", "create"):
            raise RuntimeError("invalid native Profile cron command")
        if operation.target != f"HERMES_PROFILE/{profile_id}/cron":
            raise RuntimeError("Profile cron target does not match Profile id")
        return profile_id

    @classmethod
    def _validate_operation(cls, operation: InstallOperation) -> None:
        if operation.action not in _SUPPORTED_ACTIONS:
            raise RuntimeError(
                f"unsupported install operation: {operation.component.value}:"
                f"{operation.action}"
            )
        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            if operation.component is not RuntimeComponent.PROFILE_DISTRIBUTIONS:
                raise RuntimeError("Profile install operation has wrong component")
            cls._profile_id(operation)
            return
        if operation.action == "CREATE_NATIVE_PROFILE_CRON_DUTY":
            if operation.component is not RuntimeComponent.NATIVE_PROFILE_CRON:
                raise RuntimeError("Profile cron operation has wrong component")
            cls._cron_profile_id(operation)
            return
        if operation.component is not RuntimeComponent.NATIVE_PROFILE_CRON:
            raise RuntimeError("empty cron plan operation has wrong component")
        if operation.argv:
            raise RuntimeError("empty cron plan operation must not contain a command")

    def preflight(self, operations: tuple[InstallOperation, ...]) -> None:
        for operation in operations:
            self._validate_operation(operation)

    def _run_checked(self, argv: tuple[str, ...], label: str) -> CommandResult:
        result = self._runner.run(argv)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        return result

    def apply(self, operation: InstallOperation) -> str:
        self._validate_operation(operation)
        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            profile_id = self._profile_id(operation)
            self._run_checked(operation.argv, "native Profile install")
            return _receipt({"kind": "PROFILE_INSTALL", "profile_id": profile_id})

        if operation.action == "CREATE_NATIVE_PROFILE_CRON_DUTY":
            profile_id = self._cron_profile_id(operation)
            result = self._run_checked(operation.argv, "native Profile cron create")
            match = _CREATED_JOB.search(result.stdout)
            if match is None or not _JOB_ID.fullmatch(match.group(1)):
                raise RuntimeError("native Profile cron create returned no valid job id")
            return _receipt(
                {
                    "job_id": match.group(1),
                    "kind": "PROFILE_CRON_CREATE",
                    "profile_id": profile_id,
                }
            )

        return _receipt({"kind": "EMPTY_CRON_PLAN"})

    def rollback(self, operation: InstallOperation, receipt: str) -> None:
        self._validate_operation(operation)
        payload = _load_receipt(receipt)

        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            profile_id = self._profile_id(operation)
            if payload != {"kind": "PROFILE_INSTALL", "profile_id": profile_id}:
                raise RuntimeError("Profile rollback receipt does not match operation")
            self._run_checked(
                ("hermes", "profile", "delete", profile_id, "-y"),
                "native Profile rollback",
            )
            return

        if operation.action == "CREATE_NATIVE_PROFILE_CRON_DUTY":
            profile_id = self._cron_profile_id(operation)
            job_id = payload.get("job_id")
            if (
                payload.get("kind") != "PROFILE_CRON_CREATE"
                or payload.get("profile_id") != profile_id
                or not isinstance(job_id, str)
                or not _JOB_ID.fullmatch(job_id)
            ):
                raise RuntimeError("Profile cron rollback receipt does not match operation")
            self._run_checked(
                ("hermes", "-p", profile_id, "cron", "remove", job_id),
                "native Profile cron rollback",
            )
            return

        if payload != {"kind": "EMPTY_CRON_PLAN"}:
            raise RuntimeError("empty cron rollback receipt does not match operation")
