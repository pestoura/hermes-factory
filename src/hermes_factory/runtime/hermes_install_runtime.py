from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from contextlib import suppress
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
_FACTORY_DISTRIBUTION = "hermes-factory"
_GATEWAY_BINDING_MODULE = "hermes_factory.adapters.hermes_gateway"
_GATEWAY_BINDING_PROBE = (
    "from hermes_factory.adapters.hermes_gateway import "
    "HermesGatewayHITLBinding; assert callable(HermesGatewayHITLBinding)"
)
_KANBAN_AUTO_DECOMPOSE_KEY = "kanban.auto_decompose"
_SUPPORTED_ACTIONS = {
    "STAGE_FACTORY_PACKAGE",
    "INSTALL_NATIVE_PROFILE_DISTRIBUTION",
    "CREATE_NATIVE_PROFILE_CRON_DUTY",
    "APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
    "REGISTER_DASHBOARD_PLUGIN",
    "VERIFY_GATEWAY_HITL_BINDING",
    "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
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

    Only operations with verified apply and compensation mechanisms are
    supported. The full Phase P plan therefore remains blocked by preflight
    until every remaining symbolic operation has an equally concrete mapping.
    """

    def __init__(
        self,
        *,
        command_runner: CommandRunner | None = None,
        hermes_home: Path | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._runner = command_runner or SubprocessCommandRunner()
        self._hermes_home = Path(hermes_home) if hermes_home is not None else None
        self._python_executable = python_executable or sys.executable
        if not self._python_executable.strip():
            raise ValueError("Python executable is required for Factory package installation")

    @staticmethod
    def _factory_package_source(operation: InstallOperation) -> Path:
        if operation.component is not RuntimeComponent.FACTORY_PACKAGE:
            raise RuntimeError("Factory package install operation has wrong component")
        if operation.target != "HERMES_RUNTIME_ENV":
            raise RuntimeError("Factory package target is invalid")
        if operation.argv:
            raise RuntimeError("Factory package install operation must not contain argv")
        if operation.source is None or not operation.source.strip():
            raise RuntimeError("Factory package source is required")
        source = Path(operation.source)
        if source.suffix != ".whl" or source.is_symlink() or not source.is_file():
            raise RuntimeError("Factory package source must be a regular wheel")
        if operation.source_digest is None or not operation.source_digest.startswith("sha256:"):
            raise RuntimeError("Factory package source digest is required")
        return source

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

    def _dashboard_paths(
        self,
        operation: InstallOperation,
        *,
        target_must_be_absent: bool,
    ) -> tuple[Path, Path, Path]:
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Dashboard plugin registration")
        if self._hermes_home.is_symlink() or not self._hermes_home.is_dir():
            raise RuntimeError("Hermes home must be an existing regular directory")
        if operation.source is None:
            raise RuntimeError("Dashboard plugin source is required")
        source = Path(operation.source)
        if source.is_symlink() or not source.is_dir():
            raise RuntimeError("Dashboard plugin source must be a regular directory")
        if any(path.is_symlink() for path in source.rglob("*")):
            raise RuntimeError("Dashboard plugin source must not contain symlinks")
        manifest = source / "dashboard" / "manifest.json"
        if manifest.is_symlink() or not manifest.is_file():
            raise RuntimeError("Dashboard plugin manifest is required")
        if operation.target != "HERMES_HOME/plugins/hermes-factory":
            raise RuntimeError("Dashboard plugin target is invalid")
        plugins_root = self._hermes_home / "plugins"
        if plugins_root.exists() and (plugins_root.is_symlink() or not plugins_root.is_dir()):
            raise RuntimeError("Hermes plugins root must be a regular directory")
        target = plugins_root / "hermes-factory"
        if target_must_be_absent and (target.exists() or target.is_symlink()):
            raise RuntimeError("Dashboard plugin target already exists")
        return source, target, plugins_root

    @staticmethod
    def _validate_gateway_binding(operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.GATEWAY_HITL_ADAPTER:
            raise RuntimeError("Gateway HITL binding operation has wrong component")
        if operation.source != _GATEWAY_BINDING_MODULE:
            raise RuntimeError("Gateway HITL binding source is invalid")
        if operation.target != "HERMES_GATEWAY":
            raise RuntimeError("Gateway HITL binding target is invalid")
        if operation.argv:
            raise RuntimeError("Gateway HITL binding verification must not contain argv")
        if operation.source_digest is not None:
            raise RuntimeError("Gateway HITL binding inherits Factory package identity")

    @staticmethod
    def _validate_kanban_policy(operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY:
            raise RuntimeError("Kanban high-assurance operation has wrong component")
        if operation.target != "HERMES_KANBAN":
            raise RuntimeError("Kanban high-assurance target is invalid")
        if operation.argv:
            raise RuntimeError("Kanban high-assurance operation must not contain argv")
        if operation.source is not None or operation.source_digest is not None:
            raise RuntimeError("Kanban high-assurance policy has no external source")

    def _validate_operation(
        self,
        operation: InstallOperation,
        *,
        allow_dashboard_target_exists: bool = False,
    ) -> None:
        if operation.action not in _SUPPORTED_ACTIONS:
            raise RuntimeError(
                f"unsupported install operation: {operation.component.value}:"
                f"{operation.action}"
            )
        if operation.action == "STAGE_FACTORY_PACKAGE":
            self._factory_package_source(operation)
            return
        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            if operation.component is not RuntimeComponent.PROFILE_DISTRIBUTIONS:
                raise RuntimeError("Profile install operation has wrong component")
            self._profile_id(operation)
            return
        if operation.action == "CREATE_NATIVE_PROFILE_CRON_DUTY":
            if operation.component is not RuntimeComponent.NATIVE_PROFILE_CRON:
                raise RuntimeError("Profile cron operation has wrong component")
            self._cron_profile_id(operation)
            return
        if operation.action == "REGISTER_DASHBOARD_PLUGIN":
            if operation.component is not RuntimeComponent.DASHBOARD_PLUGIN:
                raise RuntimeError("Dashboard plugin operation has wrong component")
            self._dashboard_paths(
                operation,
                target_must_be_absent=not allow_dashboard_target_exists,
            )
            return
        if operation.action == "VERIFY_GATEWAY_HITL_BINDING":
            self._validate_gateway_binding(operation)
            return
        if operation.action == "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY":
            self._validate_kanban_policy(operation)
            return
        if operation.component is not RuntimeComponent.NATIVE_PROFILE_CRON:
            raise RuntimeError("empty cron plan operation has wrong component")
        if operation.argv:
            raise RuntimeError("empty cron plan operation must not contain a command")

    def _ensure_factory_package_absent(self) -> None:
        result = self._runner.run(
            (self._python_executable, "-m", "pip", "show", _FACTORY_DISTRIBUTION)
        )
        if result.returncode == 0:
            raise RuntimeError("Factory package is already installed")
        if result.returncode != 1:
            raise RuntimeError(
                f"Factory package probe failed with exit code {result.returncode}"
            )

    def preflight(self, operations: tuple[InstallOperation, ...]) -> None:
        # First validate every operation structurally. Only after the complete
        # plan is known to be supported may read-only environment probes run.
        for operation in operations:
            self._validate_operation(operation)
        for operation in operations:
            if operation.action == "STAGE_FACTORY_PACKAGE":
                self._ensure_factory_package_absent()

    def _run_checked(self, argv: tuple[str, ...], label: str) -> CommandResult:
        result = self._runner.run(argv)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        return result

    def _read_kanban_auto_decompose(self) -> bool:
        result = self._run_checked(
            ("hermes", "config", "get", _KANBAN_AUTO_DECOMPOSE_KEY, "--json"),
            "Kanban high-assurance config read",
        )
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "kanban.auto_decompose resolved value is not valid JSON"
            ) from exc
        if not isinstance(value, bool):
            raise RuntimeError("kanban.auto_decompose resolved value must be boolean")
        return value

    def _apply_factory_package(self, operation: InstallOperation) -> str:
        source = self._factory_package_source(operation)
        # Repeat the read-only absence probe immediately before mutation to
        # close the preflight/apply race window.
        self._ensure_factory_package_absent()
        self._run_checked(
            (
                self._python_executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-input",
                str(source),
            ),
            "Factory package install",
        )
        return _receipt(
            {
                "distribution": _FACTORY_DISTRIBUTION,
                "kind": "FACTORY_PACKAGE_INSTALL",
                "source": str(source),
            }
        )

    def _apply_dashboard(self, operation: InstallOperation) -> str:
        source, target, plugins_root = self._dashboard_paths(
            operation,
            target_must_be_absent=True,
        )
        plugins_root_created = not plugins_root.exists()
        try:
            if plugins_root_created:
                plugins_root.mkdir(parents=False)
            shutil.copytree(source, target)
        except OSError:
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target)
            if plugins_root_created:
                with suppress(OSError):
                    plugins_root.rmdir()
            raise
        return _receipt(
            {
                "kind": "DASHBOARD_PLUGIN_INSTALL",
                "plugins_root_created": "true" if plugins_root_created else "false",
                "target": str(target),
            }
        )

    def _apply_kanban_policy(self) -> str:
        previous = self._read_kanban_auto_decompose()
        changed = previous
        if changed:
            self._run_checked(
                ("hermes", "config", "set", _KANBAN_AUTO_DECOMPOSE_KEY, "false"),
                "Kanban high-assurance config apply",
            )
            if self._read_kanban_auto_decompose() is not False:
                raise RuntimeError("Kanban high-assurance config verification failed")
        return _receipt(
            {
                "changed": "true" if changed else "false",
                "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
                "previous": "true" if previous else "false",
            }
        )

    def apply(self, operation: InstallOperation) -> str:
        self._validate_operation(operation)
        if operation.action == "STAGE_FACTORY_PACKAGE":
            return self._apply_factory_package(operation)
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

        if operation.action == "REGISTER_DASHBOARD_PLUGIN":
            return self._apply_dashboard(operation)

        if operation.action == "VERIFY_GATEWAY_HITL_BINDING":
            self._run_checked(
                (self._python_executable, "-c", _GATEWAY_BINDING_PROBE),
                "Gateway HITL binding verification",
            )
            return _receipt({"kind": "GATEWAY_HITL_BINDING_VERIFIED"})

        if operation.action == "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY":
            return self._apply_kanban_policy()

        return _receipt({"kind": "EMPTY_CRON_PLAN"})

    def rollback(self, operation: InstallOperation, receipt: str) -> None:
        self._validate_operation(operation, allow_dashboard_target_exists=True)
        payload = _load_receipt(receipt)

        if operation.action == "STAGE_FACTORY_PACKAGE":
            source = self._factory_package_source(operation)
            if payload != {
                "distribution": _FACTORY_DISTRIBUTION,
                "kind": "FACTORY_PACKAGE_INSTALL",
                "source": str(source),
            }:
                raise RuntimeError("Factory package rollback receipt does not match operation")
            self._run_checked(
                (
                    self._python_executable,
                    "-m",
                    "pip",
                    "uninstall",
                    "-y",
                    _FACTORY_DISTRIBUTION,
                ),
                "Factory package rollback",
            )
            return

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

        if operation.action == "REGISTER_DASHBOARD_PLUGIN":
            _, target, plugins_root = self._dashboard_paths(
                operation,
                target_must_be_absent=False,
            )
            plugins_root_created = payload.get("plugins_root_created")
            if (
                payload.get("kind") != "DASHBOARD_PLUGIN_INSTALL"
                or payload.get("target") != str(target)
                or plugins_root_created not in {"true", "false"}
            ):
                raise RuntimeError("Dashboard rollback receipt does not match operation")
            if target.is_symlink():
                raise RuntimeError("Dashboard rollback target became a symlink")
            if target.exists():
                shutil.rmtree(target)
            if plugins_root_created == "true":
                with suppress(OSError):
                    plugins_root.rmdir()
            return

        if operation.action == "VERIFY_GATEWAY_HITL_BINDING":
            if payload != {"kind": "GATEWAY_HITL_BINDING_VERIFIED"}:
                raise RuntimeError("Gateway HITL binding receipt does not match operation")
            return

        if operation.action == "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY":
            if payload not in (
                {
                    "changed": "false",
                    "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
                    "previous": "false",
                },
                {
                    "changed": "true",
                    "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
                    "previous": "true",
                },
            ):
                raise RuntimeError("Kanban high-assurance receipt does not match operation")
            if payload["changed"] == "true":
                self._run_checked(
                    ("hermes", "config", "set", _KANBAN_AUTO_DECOMPOSE_KEY, "true"),
                    "Kanban high-assurance rollback",
                )
                if self._read_kanban_auto_decompose() is not True:
                    raise RuntimeError("Kanban high-assurance rollback verification failed")
            return

        if payload != {"kind": "EMPTY_CRON_PLAN"}:
            raise RuntimeError("empty cron rollback receipt does not match operation")
