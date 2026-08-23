from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from time import sleep
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

import yaml

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.bindings import RuntimeComponentBinding
from hermes_factory.runtime.install import InstallOperation
from hermes_factory.runtime.package_candidate import (
    FactoryPackageCandidate,
    PackageCandidateError,
    load_package_candidate,
)
from hermes_factory.runtime.skill_catalog_candidate import (
    SkillCatalogCandidateError,
    load_skill_catalog_candidate,
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, argv: tuple[str, ...]) -> CommandResult: ...


class FactoryPackageProbe(Protocol):
    def current(self) -> FactoryPackageCandidate | None: ...


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


class SubprocessFactoryPackageProbe:
    def __init__(self, runner: CommandRunner, python_executable: str) -> None:
        self._runner = runner
        self._python_executable = python_executable

    def current(self) -> FactoryPackageCandidate | None:
        present = self._runner.run(
            (self._python_executable, "-m", "pip", "show", _FACTORY_DISTRIBUTION)
        )
        if present.returncode == 1:
            return None
        if present.returncode != 0:
            raise RuntimeError(
                f"Factory package probe failed with exit code {present.returncode}"
            )
        direct = self._runner.run(
            (self._python_executable, "-c", _FACTORY_DIRECT_URL_PROBE)
        )
        if direct.returncode != 0:
            raise RuntimeError("installed Factory package provenance is unavailable")
        try:
            payload = json.loads(direct.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("installed Factory package provenance is invalid") from exc
        url = payload.get("url") if isinstance(payload, dict) else None
        if not isinstance(url, str):
            raise TypeError("installed Factory package source URL is unavailable")
        parsed = urlparse(url)
        if parsed.scheme != "file":
            raise RuntimeError("installed Factory package source must be a local file URL")
        wheel = Path(unquote(parsed.path))
        match = _FACTORY_CANDIDATE_PATH.search(url)
        if match is None:
            raise RuntimeError("installed Factory package exact candidate SHA is unavailable")
        try:
            return load_package_candidate(
                manifest_path=wheel.parent / "factory-package.json",
                wheel_path=wheel,
                expected_candidate_sha=match.group(1),
            )
        except PackageCandidateError as exc:
            raise RuntimeError(str(exc)) from exc


_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CREATED_JOB = re.compile(r"^Created job:\s*(\S+)\s*$", re.MULTILINE)
_SKILL_CATALOG_TARGET = re.compile(
    r"^HERMES_HOME/factory/skill-catalog/([0-9a-fA-F]{40})$"
)
_FACTORY_DISTRIBUTION = "hermes-factory"
_FACTORY_CANDIDATE_PATH = re.compile(
    r"(?:^|/)factory-package-candidate-([0-9a-fA-F]{40})(?:/|$)"
)
_FACTORY_DIRECT_URL_PROBE = (
    "import importlib.metadata as m; "
    "d=m.distribution(\"hermes-factory\"); "
    "v=d.read_text(\"direct_url.json\"); "
    "assert v; print(v, end=\"\")"
)
_GATEWAY_BINDING_MODULE = "hermes_factory.adapters.hermes_gateway"
_GATEWAY_BINDING_PROBE = (
    "from hermes_factory.adapters.hermes_gateway import "
    "HermesGatewayHITLBinding; assert callable(HermesGatewayHITLBinding)"
)
_KANBAN_AUTO_DECOMPOSE_KEY = "kanban.auto_decompose"
_NORTHBOUND_ENTRYPOINT = "hermes_mcp_bridge.http_runner"
_NORTHBOUND_TOOLS = (
    "factory_acceptance",
    "factory_evidence",
    "factory_protected_mutation_intent",
    "factory_status",
)
_NORTHBOUND_PROTECTED_ACTIONS = (
    "ACTIVATE_PROFILE",
    "ACTIVATE_SKILL",
    "MERGE_PR",
    "RELEASE",
)
_SUPPORTED_ACTIONS = {
    "STAGE_FACTORY_PACKAGE",
    "STAGE_FACTORY_SKILL_CATALOG",
    "INSTALL_NATIVE_PROFILE_DISTRIBUTION",
    "CREATE_NATIVE_PROFILE_CRON_DUTY",
    "APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
    "REGISTER_DASHBOARD_PLUGIN",
    "REGISTER_FACTORY_PLUGIN_PROFILE",
    "ACTIVATE_FACTORY_PLUGIN_SCOPE",
    "VERIFY_FACTORY_PLUGIN_SCOPE",
    "QUIESCE_GATEWAY_FACTORY_RUNTIME",
    "VERIFY_GATEWAY_HITL_BINDING",
    "ACTIVATE_GATEWAY_FACTORY_RUNTIME",
    "VERIFY_NORTHBOUND_CONTROL_BINDING",
    "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
}


def _receipt(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _load_receipt(receipt: str) -> dict[str, object]:
    try:
        payload = json.loads(receipt)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid install rollback receipt") from exc
    if not isinstance(payload, dict):
        raise TypeError("invalid install rollback receipt")
    return payload


_GATEWAY_STABILIZATION_ATTEMPTS = 40
_GATEWAY_STABILIZATION_INTERVAL_SECONDS = 0.25


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
        factory_package_probe: FactoryPackageProbe | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._runner = command_runner or SubprocessCommandRunner()
        self._hermes_home = Path(hermes_home) if hermes_home is not None else None
        self._python_executable = python_executable or sys.executable
        python_path = Path(self._python_executable)
        self._hermes_executable = (
            str(python_path.with_name("hermes"))
            if python_path.parent != Path(".")
            else "hermes"
        )
        self._factory_package_probe = factory_package_probe
        self._sleep = sleep_fn or sleep
        self._preflight_factory_package: FactoryPackageCandidate | None = None
        self._gateway_was_running: bool | None = None
        if not self._python_executable.strip():
            raise ValueError("Python executable is required for Factory package installation")

    @staticmethod
    def _validate_rollback_candidate(candidate: FactoryPackageCandidate) -> None:
        wheel = Path(candidate.wheel_path)
        if wheel.is_symlink() or not wheel.is_file():
            raise RuntimeError("Factory rollback package wheel is unavailable")
        if digest_artifact(wheel) != candidate.artifact_digest:
            raise RuntimeError("Factory rollback package digest drift")

    def _default_factory_package_probe(self) -> FactoryPackageCandidate | None:
        return SubprocessFactoryPackageProbe(
            self._runner, self._python_executable
        ).current()

    def _current_factory_package(self) -> FactoryPackageCandidate | None:
        candidate = (
            self._factory_package_probe.current()
            if self._factory_package_probe is not None
            else self._default_factory_package_probe()
        )
        if candidate is not None:
            self._validate_rollback_candidate(candidate)
        return candidate

    @staticmethod
    def _same_factory_candidate(
        left: FactoryPackageCandidate | None,
        right: FactoryPackageCandidate | None,
    ) -> bool:
        if left is None or right is None:
            return left is right
        return (
            left.candidate_sha == right.candidate_sha
            and left.artifact_digest == right.artifact_digest
        )

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

    def _skill_catalog_paths(
        self,
        operation: InstallOperation,
        *,
        target_must_be_absent: bool,
    ) -> tuple[Path, Path, Path, Path, str]:
        if operation.component is not RuntimeComponent.FACTORY_SKILLS:
            raise RuntimeError("Factory Skill catalog operation has wrong component")
        if operation.argv:
            raise RuntimeError("Factory Skill catalog operation must not contain argv")
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Factory Skill catalog staging")
        if self._hermes_home.is_symlink() or not self._hermes_home.is_dir():
            raise RuntimeError("Hermes home must be an existing regular directory")
        if operation.source is None or not operation.source.strip():
            raise RuntimeError("Factory Skill catalog source is required")
        if operation.source_digest is None or not operation.source_digest.startswith("sha256:"):
            raise RuntimeError("Factory Skill catalog source digest is required")
        match = _SKILL_CATALOG_TARGET.fullmatch(operation.target or "")
        if match is None:
            raise RuntimeError("Factory Skill catalog target is invalid")
        candidate_sha = match.group(1).lower()
        source = Path(operation.source)
        try:
            candidate = load_skill_catalog_candidate(
                candidate_root=source,
                expected_candidate_sha=candidate_sha,
            )
        except SkillCatalogCandidateError as exc:
            raise RuntimeError(str(exc)) from exc
        if candidate.artifact_digest != operation.source_digest:
            raise RuntimeError(
                "Factory Skill catalog source digest mismatch: "
                f"expected {operation.source_digest}, observed {candidate.artifact_digest}"
            )

        factory_root = self._hermes_home / "factory"
        catalog_root = factory_root / "skill-catalog"
        for path, label in (
            (factory_root, "Factory private root"),
            (catalog_root, "Factory Skill catalog root"),
        ):
            if path.exists() and (path.is_symlink() or not path.is_dir()):
                raise RuntimeError(f"{label} must be a regular directory")
        target = catalog_root / candidate_sha
        if target_must_be_absent and (target.exists() or target.is_symlink()):
            raise RuntimeError("Factory Skill catalog target already exists")
        return source, target, factory_root, catalog_root, candidate_sha

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

    def _profile_plugin_paths(
        self,
        operation: InstallOperation,
        *,
        target_must_be_absent: bool,
    ) -> tuple[str, Path, Path, Path]:
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Factory Profile plugin registration")
        if operation.source is None:
            raise RuntimeError("Factory Profile plugin source is required")
        source = Path(operation.source)
        if source.is_symlink() or not source.is_dir():
            raise RuntimeError("Factory Profile plugin source must be a regular directory")
        if any(path.is_symlink() for path in source.rglob("*")):
            raise RuntimeError("Factory Profile plugin source must not contain symlinks")
        manifest = source / "plugin.yaml"
        if manifest.is_symlink() or not manifest.is_file():
            raise RuntimeError("Factory Profile plugin manifest is required")
        prefix = "HERMES_HOME/profiles/"
        suffix = "/plugins/hermes-factory"
        target_text = operation.target or ""
        if not target_text.startswith(prefix) or not target_text.endswith(suffix):
            raise RuntimeError("Factory Profile plugin target is invalid")
        profile_id = target_text[len(prefix):-len(suffix)]
        if not _PROFILE_ID.fullmatch(profile_id):
            raise RuntimeError("Factory Profile plugin target Profile id is invalid")
        profile_home = self._hermes_home / "profiles" / profile_id
        if profile_home.is_symlink() or not profile_home.is_dir():
            raise RuntimeError("Factory Profile plugin target Profile is unavailable")
        plugins_root = profile_home / "plugins"
        if plugins_root.exists() and (plugins_root.is_symlink() or not plugins_root.is_dir()):
            raise RuntimeError("Factory Profile plugins root must be a regular directory")
        target = plugins_root / "hermes-factory"
        if target_must_be_absent and (target.exists() or target.is_symlink()):
            raise RuntimeError("Factory Profile plugin target already exists")
        if operation.source_digest is not None and digest_artifact(source) != operation.source_digest:
            raise RuntimeError("Factory Profile plugin source digest drift")
        return profile_id, source, target, plugins_root

    def _factory_plugin_scope(
        self, operation: InstallOperation
    ) -> tuple[str, Path, tuple[str, ...]]:
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Factory plugin scope operations")
        target = operation.target or ""
        if target == "HERMES_HOME":
            return target, self._hermes_home, ()
        prefix = "HERMES_HOME/profiles/"
        if not target.startswith(prefix):
            raise RuntimeError("Factory plugin scope target is invalid")
        profile_id = target[len(prefix):]
        if not _PROFILE_ID.fullmatch(profile_id):
            raise RuntimeError("Factory plugin scope Profile id is invalid")
        profile_home = self._hermes_home / "profiles" / profile_id
        if profile_home.is_symlink() or not profile_home.is_dir():
            raise RuntimeError("Factory plugin scope Profile is unavailable")
        return target, profile_home, ("-p", profile_id)

    def _validate_factory_plugin_activation(self, operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.DASHBOARD_PLUGIN:
            raise RuntimeError("Factory plugin activation operation has wrong component")
        target, _, profile_prefix = self._factory_plugin_scope(operation)
        expected = (
            "hermes",
            *profile_prefix,
            "plugins",
            "enable",
            "hermes-factory",
            "--no-allow-tool-override",
        )
        if operation.argv != expected:
            raise RuntimeError(f"Factory plugin activation command is invalid for {target}")
        if operation.source is not None or operation.source_digest is not None:
            raise RuntimeError("Factory plugin activation must not contain source identity")

    def _validate_factory_plugin_verification(self, operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.DASHBOARD_PLUGIN:
            raise RuntimeError("Factory plugin verification operation has wrong component")
        self._factory_plugin_scope(operation)
        if operation.argv:
            raise RuntimeError("Factory plugin verification must not contain argv")
        if operation.source is not None or operation.source_digest is not None:
            raise RuntimeError("Factory plugin verification must not contain source identity")

    @staticmethod
    def _raw_plugin_snapshot(scope_home: Path) -> dict[str, object]:
        config_path = scope_home / "config.yaml"
        if not config_path.exists():
            plugins: dict[str, object] = {}
        else:
            if config_path.is_symlink() or not config_path.is_file():
                raise RuntimeError("Factory plugin scope config must be a regular file")
            try:
                payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except (OSError, UnicodeError, yaml.YAMLError) as exc:
                raise RuntimeError("Factory plugin scope config is invalid") from exc
            if not isinstance(payload, dict):
                raise TypeError("Factory plugin scope config must contain a mapping")
            raw_plugins = payload.get("plugins", {})
            if raw_plugins is None:
                raw_plugins = {}
            if not isinstance(raw_plugins, dict):
                raise TypeError("Factory plugin scope plugins config must be a mapping")
            plugins = raw_plugins

        def capture(key: str, expected_type: type) -> dict[str, object]:
            if key not in plugins:
                return {"present": False, "value": None}
            value = plugins[key]
            if not isinstance(value, expected_type):
                raise TypeError(f"Factory plugin scope plugins.{key} has invalid type")
            return {"present": True, "value": value}

        enabled = capture("enabled", list)
        disabled = capture("disabled", list)
        for field in (enabled, disabled):
            value = field["value"]
            if value is not None:
                if not isinstance(value, list):
                    raise TypeError("Factory plugin enabled/disabled config must be a list")
                if any(not isinstance(item, str) for item in value):
                    raise TypeError("Factory plugin enabled/disabled entries must be strings")
        entries = plugins.get("entries", {})
        if entries is None:
            entries = {}
        if not isinstance(entries, dict):
            raise TypeError("Factory plugin scope plugins.entries must be a mapping")
        entry_present = "hermes-factory" in entries
        entry = entries.get("hermes-factory")
        if entry_present and not isinstance(entry, dict):
            raise TypeError("Factory plugin scope entry must be a mapping")
        return {
            "enabled": enabled,
            "disabled": disabled,
            "entry": {"present": entry_present, "value": entry if entry_present else None},
        }

    @staticmethod
    def _compact_json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _snapshot_field(snapshot: dict[str, object], name: str) -> tuple[bool, object]:
        field = snapshot.get(name)
        if not isinstance(field, dict) or field.get("present") not in {True, False}:
            raise RuntimeError("Factory plugin activation receipt snapshot is invalid")
        return bool(field["present"]), field.get("value")

    @staticmethod
    def _raw_plugin_key_present(scope_home: Path, name: str) -> bool:
        snapshot = HermesJarvasInstallRuntime._raw_plugin_snapshot(scope_home)
        present, _ = HermesJarvasInstallRuntime._snapshot_field(snapshot, name)
        return present

    def _scope_config_argv(
        self, profile_prefix: tuple[str, ...], *args: str
    ) -> tuple[str, ...]:
        return ("hermes", *profile_prefix, "config", *args)

    def _restore_factory_plugin_snapshot(
        self,
        *,
        scope_home: Path,
        profile_prefix: tuple[str, ...],
        snapshot: dict[str, object],
        label: str,
    ) -> None:
        fields = (
            ("enabled", "plugins.enabled"),
            ("disabled", "plugins.disabled"),
            ("entry", "plugins.entries.hermes-factory"),
        )
        for name, key in fields:
            present, value = self._snapshot_field(snapshot, name)
            if present:
                self._run_checked(
                    self._scope_config_argv(
                        profile_prefix, "set", key, self._compact_json(value)
                    ),
                    label,
                )
            elif self._raw_plugin_key_present(scope_home, name):
                self._run_checked(
                    self._scope_config_argv(profile_prefix, "unset", key),
                    label,
                )

    def _read_scope_json(
        self, profile_prefix: tuple[str, ...], key: str, *, label: str
    ) -> object:
        result = self._run_checked(
            self._scope_config_argv(profile_prefix, "get", key, "--json"), label
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label} returned invalid JSON") from exc

    def _apply_factory_plugin_activation(self, operation: InstallOperation) -> str:
        scope, scope_home, profile_prefix = self._factory_plugin_scope(operation)
        snapshot = self._raw_plugin_snapshot(scope_home)
        try:
            self._run_checked(operation.argv, "Factory plugin native activation")
            enabled = self._read_scope_json(
                profile_prefix,
                "plugins.enabled",
                label="Factory plugin enabled-state verification",
            )
            if not isinstance(enabled, list) or "hermes-factory" not in enabled:
                raise RuntimeError("Factory plugin activation was not persisted")
            override = self._read_scope_json(
                profile_prefix,
                "plugins.entries.hermes-factory.allow_tool_override",
                label="Factory plugin tool-override verification",
            )
            if override is not False:
                raise RuntimeError("Factory plugin tool override must remain disabled")
        except Exception:
            try:
                self._restore_factory_plugin_snapshot(
                    scope_home=scope_home,
                    profile_prefix=profile_prefix,
                    snapshot=snapshot,
                    label="Factory plugin activation compensation",
                )
            except Exception as compensation_exc:
                raise RuntimeError(
                    "Factory plugin activation compensation failed; runtime state is unknown"
                ) from compensation_exc
            raise
        return _receipt(
            {
                "kind": "FACTORY_PLUGIN_SCOPE_ACTIVATE",
                "scope": scope,
                "snapshot": snapshot,
            }
        )

    def _apply_factory_plugin_verification(self, operation: InstallOperation) -> str:
        scope, scope_home, _ = self._factory_plugin_scope(operation)
        probe = (
            'from hermes_cli.plugins import PluginManager; '
            'm=PluginManager(); m.discover_and_load(force=True); '
            'assert m.has_hook("pre_tool_call"); '
            'assert m.has_hook("kanban_task_completed")'
        )
        self._run_checked(
            ("env", f"HERMES_HOME={scope_home}", self._python_executable, "-c", probe),
            "Factory plugin callback verification",
        )
        return _receipt({"kind": "FACTORY_PLUGIN_SCOPE_VERIFIED", "scope": scope})

    def _profile_plugin_backup_path(self, candidate_sha: str, profile_id: str) -> Path:
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Factory Profile plugin upgrade")
        return (
            self._hermes_home / "factory" / "profile-plugin-catalog" /
            candidate_sha / profile_id
        )

    def _profile_plugin_target_exists(self, operation: InstallOperation) -> bool:
        _, _, target, _ = self._profile_plugin_paths(
            operation, target_must_be_absent=False
        )
        return target.exists() or target.is_symlink()

    def _validate_profile_plugin_upgrade(self, operation: InstallOperation) -> None:
        profile_id, source, target, _ = self._profile_plugin_paths(
            operation, target_must_be_absent=False
        )
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError("Factory Profile plugin upgrade target must be a regular directory")
        if operation.source_digest is not None and digest_artifact(source) != operation.source_digest:
            raise RuntimeError("Factory Profile plugin source digest drift")
        if operation.source_digest is not None and digest_artifact(target) == operation.source_digest:
            return
        previous = self._preflight_factory_package
        if previous is None:
            raise RuntimeError("Factory Profile plugin upgrade requires previous Factory package identity")
        backup = self._profile_plugin_backup_path(previous.candidate_sha, profile_id)
        if backup.is_symlink():
            raise RuntimeError("Factory Profile plugin backup path must not be a symlink")
        if backup.exists() and (
            not backup.is_dir() or digest_artifact(backup) != digest_artifact(target)
        ):
            raise RuntimeError("Factory Profile plugin rollback backup conflicts with live target")

    def _apply_profile_plugin(self, operation: InstallOperation) -> str:
        profile_id, source, target, plugins_root = self._profile_plugin_paths(
            operation, target_must_be_absent=False
        )
        plugins_root_created = not plugins_root.exists()
        if not target.exists():
            try:
                if plugins_root_created:
                    plugins_root.mkdir(parents=False)
                shutil.copytree(source, target)
                if operation.source_digest is not None and digest_artifact(target) != operation.source_digest:
                    raise RuntimeError("Factory Profile plugin staged digest mismatch")
            except Exception:
                if target.exists() and not target.is_symlink():
                    shutil.rmtree(target)
                if plugins_root_created:
                    with suppress(OSError):
                        plugins_root.rmdir()
                raise
            return _receipt(
                {
                    "kind": "FACTORY_PLUGIN_PROFILE_INSTALL",
                    "plugins_root_created": "true" if plugins_root_created else "false",
                    "profile_id": profile_id,
                    "target": str(target),
                }
            )
        if operation.source_digest is not None and digest_artifact(target) == operation.source_digest:
            return _receipt(
                {
                    "kind": "FACTORY_PLUGIN_PROFILE_REUSE",
                    "profile_id": profile_id,
                    "target": str(target),
                }
            )
        self._validate_profile_plugin_upgrade(operation)
        previous = self._preflight_factory_package
        if previous is None:
            raise RuntimeError("Factory Profile plugin upgrade lacks previous candidate identity")
        backup = self._profile_plugin_backup_path(previous.candidate_sha, profile_id)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copytree(target, backup)
        staged = plugins_root / ".hermes-factory-upgrade"
        if staged.exists() or staged.is_symlink():
            raise RuntimeError("Factory Profile plugin staged upgrade path already exists")
        try:
            shutil.copytree(source, staged)
            if operation.source_digest is not None and digest_artifact(staged) != operation.source_digest:
                raise RuntimeError("Factory Profile plugin staged digest mismatch")
            shutil.rmtree(target)
            staged.rename(target)
        except Exception:
            if staged.exists() and not staged.is_symlink():
                shutil.rmtree(staged)
            if not target.exists() and backup.is_dir():
                shutil.copytree(backup, target)
            raise
        return _receipt(
            {
                "backup": str(backup),
                "kind": "FACTORY_PLUGIN_PROFILE_UPGRADE",
                "previous_candidate_sha": previous.candidate_sha,
                "profile_id": profile_id,
                "target": str(target),
            }
        )

    @staticmethod
    def _validate_gateway_runtime_operation(operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.GATEWAY_HITL_ADAPTER:
            raise RuntimeError("Gateway runtime operation has wrong component")
        if operation.target != "HERMES_GATEWAY":
            raise RuntimeError("Gateway runtime target is invalid")
        if operation.argv:
            raise RuntimeError("Gateway runtime operation must not contain argv")
        if operation.source is not None or operation.source_digest is not None:
            raise RuntimeError("Gateway runtime operation must not contain source identity")


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
    def _validate_northbound_binding(operation: InstallOperation) -> None:
        if operation.component is not RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION:
            raise RuntimeError("northbound control binding operation has wrong component")
        if operation.target != "HERMES_MCP_BRIDGE":
            raise RuntimeError("northbound control binding target is invalid")
        if operation.argv:
            raise RuntimeError("northbound control binding verification must not contain argv")
        if operation.source is None or not operation.source.strip():
            raise RuntimeError("northbound control binding source is required")
        source = Path(operation.source)
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("northbound control binding source must be a regular file")
        if operation.source_digest is None or digest_artifact(source) != operation.source_digest:
            raise RuntimeError("northbound control binding source digest mismatch")
        try:
            payload = yaml.safe_load(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise RuntimeError("northbound control binding could not be loaded") from exc
        if not isinstance(payload, dict):
            raise TypeError("northbound control binding must be a mapping")
        try:
            binding = RuntimeComponentBinding.from_mapping(payload)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("northbound control binding contract is invalid") from exc
        if binding.component is not RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION:
            raise RuntimeError("northbound control binding component is invalid")
        if binding.admission_state is not AdmissionEvidenceState.PASS:
            raise RuntimeError("northbound control binding verification_state must be PASS")
        if payload.get("default_enabled") is not False:
            raise RuntimeError("northbound control binding default_enabled must be false")
        if payload.get("internal_factory_ipc") is not False:
            raise RuntimeError("northbound control binding internal_factory_ipc must be false")
        if payload.get("mutation_execution") is not False:
            raise RuntimeError("northbound control binding mutation_execution must be false")
        if payload.get("production_entrypoint") != _NORTHBOUND_ENTRYPOINT:
            raise RuntimeError("northbound control binding production_entrypoint is invalid")
        if tuple(payload.get("tools", ())) != _NORTHBOUND_TOOLS:
            raise RuntimeError("northbound control binding tools are invalid")
        if tuple(payload.get("protected_actions", ())) != _NORTHBOUND_PROTECTED_ACTIONS:
            raise RuntimeError("northbound control binding protected_actions are invalid")

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
        allow_skill_catalog_target_exists: bool = False,
    ) -> None:
        if operation.action not in _SUPPORTED_ACTIONS:
            raise RuntimeError(
                f"unsupported install operation: {operation.component.value}:"
                f"{operation.action}"
            )
        if operation.action == "STAGE_FACTORY_PACKAGE":
            self._factory_package_source(operation)
            return
        if operation.action == "STAGE_FACTORY_SKILL_CATALOG":
            self._skill_catalog_paths(
                operation,
                target_must_be_absent=not allow_skill_catalog_target_exists,
            )
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
        if operation.action == "REGISTER_FACTORY_PLUGIN_PROFILE":
            if operation.component is not RuntimeComponent.DASHBOARD_PLUGIN:
                raise RuntimeError("Factory Profile plugin operation has wrong component")
            self._profile_plugin_paths(
                operation,
                target_must_be_absent=not allow_dashboard_target_exists,
            )
            return
        if operation.action == "ACTIVATE_FACTORY_PLUGIN_SCOPE":
            self._validate_factory_plugin_activation(operation)
            return
        if operation.action == "VERIFY_FACTORY_PLUGIN_SCOPE":
            self._validate_factory_plugin_verification(operation)
            return
        if operation.action in {
            "QUIESCE_GATEWAY_FACTORY_RUNTIME",
            "ACTIVATE_GATEWAY_FACTORY_RUNTIME",
        }:
            self._validate_gateway_runtime_operation(operation)
            return
        if operation.action == "VERIFY_GATEWAY_HITL_BINDING":
            self._validate_gateway_binding(operation)
            return
        if operation.action == "VERIFY_NORTHBOUND_CONTROL_BINDING":
            self._validate_northbound_binding(operation)
            return
        if operation.action == "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY":
            self._validate_kanban_policy(operation)
            return
        if operation.component is not RuntimeComponent.NATIVE_PROFILE_CRON:
            raise RuntimeError("empty cron plan operation has wrong component")
        if operation.argv:
            raise RuntimeError("empty cron plan operation must not contain a command")

    @staticmethod
    def _normalized_profile_distribution_manifest(
        path: Path, *, installed: bool
    ) -> dict[str, object]:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Profile distribution manifest must be a regular file")
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise RuntimeError("Profile distribution manifest is invalid") from exc
        if not isinstance(payload, dict):
            raise TypeError("Profile distribution manifest must contain a mapping")
        normalized = dict(payload)
        if installed:
            normalized.pop("source", None)
            normalized.pop("installed_at", None)
        elif "source" in normalized or "installed_at" in normalized:
            raise RuntimeError("source Profile manifest contains runtime-owned metadata")
        owned = normalized.get("distribution_owned")
        if owned is not None:
            if not isinstance(owned, list) or any(not isinstance(item, str) for item in owned):
                raise RuntimeError("Profile distribution ownership manifest is invalid")
            normalized["distribution_owned"] = sorted(
                item.rstrip("/") for item in owned
            )
        return normalized

    def _profile_reuse_state(
        self, operation: InstallOperation
    ) -> tuple[str, Path, Path] | None:
        profile_id = self._profile_id(operation)
        source = Path(operation.source or "")
        if operation.source_digest is not None:
            observed_source = digest_artifact(source)
            if observed_source != operation.source_digest:
                raise RuntimeError("Profile distribution source digest drift")
        if self._hermes_home is None:
            return None
        target = self._hermes_home / "profiles" / profile_id
        if not target.exists():
            return None
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError("installed Profile target must be a regular directory")
        for entry in source.rglob("*"):
            if entry.is_symlink():
                raise RuntimeError("Profile distribution source contains a symlink")
            relative = entry.relative_to(source)
            installed = target / relative
            if entry.is_dir():
                if installed.is_symlink() or not installed.is_dir():
                    raise RuntimeError("Profile managed distribution drift")
            elif entry.is_file():
                if installed.is_symlink() or not installed.is_file():
                    raise RuntimeError("Profile managed distribution drift")
                if relative == Path("distribution.yaml"):
                    source_manifest = self._normalized_profile_distribution_manifest(
                        entry, installed=False
                    )
                    installed_manifest = self._normalized_profile_distribution_manifest(
                        installed, installed=True
                    )
                    if source_manifest != installed_manifest:
                        raise RuntimeError("Profile managed distribution drift")
                elif relative == Path("config.yaml"):
                    # Native Hermes Profile updates preserve config.yaml unless
                    # --force-config is requested. Factory never requests that
                    # destructive override, so runtime-owned config mutations
                    # (schema version, plugin activation, user overrides) are
                    # intentionally compatible with Profile reuse.
                    continue
                elif digest_artifact(entry) != digest_artifact(installed):
                    raise RuntimeError("Profile managed distribution drift")
            else:
                raise RuntimeError("Profile distribution contains unsupported entry")
        return profile_id, source, target

    def _dashboard_target_exists(self, operation: InstallOperation) -> bool:
        _, target, _ = self._dashboard_paths(operation, target_must_be_absent=False)
        return target.exists() or target.is_symlink()

    def _dashboard_backup_path(self, candidate_sha: str) -> Path:
        if self._hermes_home is None:
            raise RuntimeError("Hermes home is required for Dashboard plugin upgrade")
        return self._hermes_home / "factory" / "dashboard-plugin-catalog" / candidate_sha

    def _validate_dashboard_upgrade(self, operation: InstallOperation) -> None:
        source, target, _ = self._dashboard_paths(operation, target_must_be_absent=False)
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError("Dashboard plugin upgrade target must be a regular directory")
        previous = self._preflight_factory_package
        if previous is None:
            raise RuntimeError("Dashboard plugin upgrade requires previous Factory package identity")
        self._validate_rollback_candidate(previous)
        if operation.source_digest is not None and digest_artifact(source) != operation.source_digest:
            raise RuntimeError("Dashboard plugin source digest drift")
        backup = self._dashboard_backup_path(previous.candidate_sha)
        if backup.is_symlink():
            raise RuntimeError("Dashboard plugin backup path must not be a symlink")
        if backup.exists() and (
            not backup.is_dir() or digest_artifact(backup) != digest_artifact(target)
        ):
            raise RuntimeError("Dashboard plugin rollback backup conflicts with live target")

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
        # Validate the complete operation set before any mutation. Upgrade mode
        # is opt-in through an exact-candidate package probe; legacy first-install
        # behavior remains unchanged when no probe is supplied.
        allow_dashboard_upgrade = self._factory_package_probe is not None
        for operation in operations:
            self._validate_operation(
                operation, allow_dashboard_target_exists=allow_dashboard_upgrade
            )

        if self._factory_package_probe is not None:
            needs_package_identity = any(
                operation.action == "STAGE_FACTORY_PACKAGE"
                or (
                    operation.action == "REGISTER_DASHBOARD_PLUGIN"
                    and self._dashboard_target_exists(operation)
                )
                or (
                    operation.action == "REGISTER_FACTORY_PLUGIN_PROFILE"
                    and self._profile_plugin_target_exists(operation)
                )
                for operation in operations
            )
            if needs_package_identity:
                self._preflight_factory_package = self._current_factory_package()

        for operation in operations:
            if operation.action == "STAGE_FACTORY_PACKAGE":
                if self._factory_package_probe is None:
                    self._ensure_factory_package_absent()
                elif self._preflight_factory_package is not None:
                    self._validate_rollback_candidate(self._preflight_factory_package)
            elif operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
                self._profile_reuse_state(operation)
            elif (
                operation.action == "REGISTER_DASHBOARD_PLUGIN"
                and self._dashboard_target_exists(operation)
            ):
                self._validate_dashboard_upgrade(operation)
            elif (
                operation.action == "REGISTER_FACTORY_PLUGIN_PROFILE"
                and self._profile_plugin_target_exists(operation)
            ):
                self._validate_profile_plugin_upgrade(operation)
            elif operation.action == "ACTIVATE_FACTORY_PLUGIN_SCOPE":
                _, scope_home, _ = self._factory_plugin_scope(operation)
                self._raw_plugin_snapshot(scope_home)

    def _run_checked(self, argv: tuple[str, ...], label: str) -> CommandResult:
        result = self._runner.run(argv)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        return result

    def _gateway_state(self) -> bool | None:
        result = self._runner.run((self._hermes_executable, "gateway", "status"))
        text = f"{result.stdout}\n{result.stderr}".lower()
        if "not running" in text or "inactive (dead)" in text or "inactive: inactive" in text:
            return False
        if "service is running" in text or "active (running)" in text:
            if result.returncode != 0:
                raise RuntimeError("Gateway status contradicts command exit code")
            return True
        if any(
            marker in text
            for marker in (
                "activating",
                "deactivating",
                "stopping",
                "starting",
            )
        ):
            return None
        raise RuntimeError(
            f"Gateway runtime status is ambiguous (exit code {result.returncode})"
        )

    def _gateway_running(self) -> bool:
        state = self._gateway_state()
        if state is None:
            raise RuntimeError("Gateway runtime status is transitional")
        return state

    def _gateway_transition(self, action: str, *, running: bool, label: str) -> None:
        self._run_checked((self._hermes_executable, "gateway", action), label)
        for attempt in range(_GATEWAY_STABILIZATION_ATTEMPTS):
            state = self._gateway_state()
            if state is running:
                return
            if attempt + 1 < _GATEWAY_STABILIZATION_ATTEMPTS:
                self._sleep(_GATEWAY_STABILIZATION_INTERVAL_SECONDS)
        raise RuntimeError(f"{label} verification failed")

    def _apply_gateway_quiesce(self) -> str:
        was_running = self._gateway_running()
        self._gateway_was_running = was_running
        if was_running:
            try:
                self._gateway_transition(
                    "stop", running=False, label="Factory Gateway quiesce"
                )
            except Exception:
                with suppress(Exception):
                    self._gateway_transition(
                        "start", running=True, label="Factory Gateway quiesce recovery"
                    )
                self._gateway_was_running = None
                raise
        return _receipt(
            {
                "kind": "GATEWAY_RUNTIME_QUIESCE",
                "was_running": "true" if was_running else "false",
            }
        )

    def _apply_gateway_activate(self) -> str:
        if self._gateway_was_running is None:
            raise RuntimeError("Gateway activation requires prior quiesce in this execution")
        started = self._gateway_was_running
        if started:
            try:
                self._gateway_transition(
                    "start", running=True, label="Factory Gateway activation"
                )
            except Exception:
                with suppress(Exception):
                    self._runner.run((self._hermes_executable, "gateway", "stop"))
                raise
        return _receipt(
            {
                "kind": "GATEWAY_RUNTIME_ACTIVATE",
                "started": "true" if started else "false",
            }
        )

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
            raise TypeError("kanban.auto_decompose resolved value must be boolean")
        return value

    def _restore_kanban_auto_decompose_true(self, *, label: str) -> None:
        self._run_checked(
            ("hermes", "config", "set", _KANBAN_AUTO_DECOMPOSE_KEY, "true"),
            label,
        )
        if self._read_kanban_auto_decompose() is not True:
            raise RuntimeError(f"{label} verification failed")

    def _apply_factory_package(self, operation: InstallOperation) -> str:
        source = self._factory_package_source(operation)
        if self._factory_package_probe is None:
            # Legacy first install remains fail-closed when a package exists.
            self._ensure_factory_package_absent()
            self._run_checked(
                (
                    self._python_executable, "-m", "pip", "install",
                    "--no-deps", "--no-input", str(source),
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

        previous = self._preflight_factory_package
        current = self._current_factory_package()
        if not self._same_factory_candidate(previous, current):
            raise RuntimeError("Factory package identity changed after preflight")
        if current is None:
            raise RuntimeError("Factory package upgrade requires an installed rollback candidate")
        if current.artifact_digest == operation.source_digest:
            return _receipt(
                {
                    "candidate_sha": current.candidate_sha,
                    "kind": "FACTORY_PACKAGE_REUSE",
                    "source": str(current.wheel_path),
                }
            )

        self._run_checked(
            (
                self._python_executable, "-m", "pip", "install", "--force-reinstall",
                "--no-deps", "--no-input", str(source),
            ),
            "Factory package upgrade",
        )
        observed = self._current_factory_package()
        if observed is None or observed.artifact_digest != operation.source_digest:
            raise RuntimeError("Factory package upgrade exact candidate verification failed")
        return _receipt(
            {
                "distribution": _FACTORY_DISTRIBUTION,
                "kind": "FACTORY_PACKAGE_UPGRADE",
                "source": str(source),
                "rollback_candidate_sha": current.candidate_sha,
                "rollback_source": str(current.wheel_path),
                "rollback_digest": current.artifact_digest,
            }
        )

    def _apply_skill_catalog(self, operation: InstallOperation) -> str:
        source, target, factory_root, catalog_root, candidate_sha = self._skill_catalog_paths(
            operation,
            target_must_be_absent=True,
        )
        factory_root_created = not factory_root.exists()
        catalog_root_created = not catalog_root.exists()
        try:
            if factory_root_created:
                factory_root.mkdir(parents=False)
            if catalog_root_created:
                catalog_root.mkdir(parents=False)
            shutil.copytree(source, target)
            observed_digest = digest_artifact(target)
            if observed_digest != operation.source_digest:
                raise RuntimeError(
                    "Factory Skill catalog staged digest mismatch: "
                    f"expected {operation.source_digest}, observed {observed_digest}"
                )
        except Exception:
            if target.exists() and not target.is_symlink():
                shutil.rmtree(target)
            if catalog_root_created:
                with suppress(OSError):
                    catalog_root.rmdir()
            if factory_root_created:
                with suppress(OSError):
                    factory_root.rmdir()
            raise
        return _receipt(
            {
                "candidate_sha": candidate_sha,
                "catalog_root_created": "true" if catalog_root_created else "false",
                "factory_root_created": "true" if factory_root_created else "false",
                "kind": "FACTORY_SKILL_CATALOG_STAGE",
                "target": str(target),
            }
        )

    def _apply_dashboard(self, operation: InstallOperation) -> str:
        source, target, plugins_root = self._dashboard_paths(
            operation, target_must_be_absent=False
        )
        plugins_root_created = not plugins_root.exists()
        if not target.exists():
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

        self._validate_dashboard_upgrade(operation)
        previous = self._preflight_factory_package
        if previous is None:
            raise RuntimeError("Dashboard plugin upgrade lacks previous candidate identity")
        backup = self._dashboard_backup_path(previous.candidate_sha)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copytree(target, backup)
        staged = plugins_root / ".hermes-factory-upgrade"
        if staged.exists() or staged.is_symlink():
            raise RuntimeError("Dashboard plugin staged upgrade path already exists")
        try:
            shutil.copytree(source, staged)
            if operation.source_digest is not None and digest_artifact(staged) != operation.source_digest:
                raise RuntimeError("Dashboard plugin staged digest mismatch")
            shutil.rmtree(target)
            staged.rename(target)
        except Exception:
            if staged.exists() and not staged.is_symlink():
                shutil.rmtree(staged)
            if not target.exists() and backup.is_dir():
                shutil.copytree(backup, target)
            raise
        return _receipt(
            {
                "backup": str(backup),
                "kind": "DASHBOARD_PLUGIN_UPGRADE",
                "previous_candidate_sha": previous.candidate_sha,
                "target": str(target),
            }
        )

    def _apply_kanban_policy(self) -> str:
        previous = self._read_kanban_auto_decompose()
        changed = previous
        if changed:
            try:
                self._run_checked(
                    ("hermes", "config", "set", _KANBAN_AUTO_DECOMPOSE_KEY, "false"),
                    "Kanban high-assurance config apply",
                )
                if self._read_kanban_auto_decompose() is not False:
                    raise RuntimeError("Kanban high-assurance config verification failed")
            except (RuntimeError, TypeError):
                try:
                    self._restore_kanban_auto_decompose_true(
                        label="Kanban high-assurance compensation"
                    )
                except (RuntimeError, TypeError) as compensation_exc:
                    raise RuntimeError(
                        "Kanban high-assurance compensation failed; runtime state is unknown"
                    ) from compensation_exc
                raise
        return _receipt(
            {
                "changed": "true" if changed else "false",
                "kind": "KANBAN_HIGH_ASSURANCE_POLICY",
                "previous": "true" if previous else "false",
            }
        )

    def apply(self, operation: InstallOperation) -> str:
        self._validate_operation(
            operation,
            allow_dashboard_target_exists=self._factory_package_probe is not None,
        )
        if operation.action == "STAGE_FACTORY_PACKAGE":
            return self._apply_factory_package(operation)
        if operation.action == "STAGE_FACTORY_SKILL_CATALOG":
            return self._apply_skill_catalog(operation)
        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            reuse = self._profile_reuse_state(operation)
            if reuse is not None:
                profile_id, _, _ = reuse
                return _receipt(
                    {
                        "kind": "PROFILE_REUSE",
                        "profile_id": profile_id,
                        "source_digest": operation.source_digest or "",
                    }
                )
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

        if operation.action == "QUIESCE_GATEWAY_FACTORY_RUNTIME":
            return self._apply_gateway_quiesce()

        if operation.action == "REGISTER_DASHBOARD_PLUGIN":
            return self._apply_dashboard(operation)

        if operation.action == "REGISTER_FACTORY_PLUGIN_PROFILE":
            return self._apply_profile_plugin(operation)

        if operation.action == "ACTIVATE_FACTORY_PLUGIN_SCOPE":
            return self._apply_factory_plugin_activation(operation)

        if operation.action == "VERIFY_FACTORY_PLUGIN_SCOPE":
            return self._apply_factory_plugin_verification(operation)

        if operation.action == "VERIFY_GATEWAY_HITL_BINDING":
            self._run_checked(
                (self._python_executable, "-c", _GATEWAY_BINDING_PROBE),
                "Gateway HITL binding verification",
            )
            return _receipt({"kind": "GATEWAY_HITL_BINDING_VERIFIED"})

        if operation.action == "VERIFY_NORTHBOUND_CONTROL_BINDING":
            self._validate_northbound_binding(operation)
            return _receipt({"kind": "NORTHBOUND_CONTROL_BINDING_VERIFIED"})

        if operation.action == "ACTIVATE_GATEWAY_FACTORY_RUNTIME":
            return self._apply_gateway_activate()

        if operation.action == "APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY":
            return self._apply_kanban_policy()

        return _receipt({"kind": "EMPTY_CRON_PLAN"})

    def rollback(self, operation: InstallOperation, receipt: str) -> None:
        self._validate_operation(
            operation,
            allow_dashboard_target_exists=True,
            allow_skill_catalog_target_exists=True,
        )
        payload = _load_receipt(receipt)

        if operation.action == "STAGE_FACTORY_PACKAGE":
            source = self._factory_package_source(operation)
            kind = payload.get("kind")
            if kind == "FACTORY_PACKAGE_REUSE":
                if not isinstance(payload.get("candidate_sha"), str):
                    raise RuntimeError("Factory package reuse receipt is invalid")
                return
            if kind == "FACTORY_PACKAGE_UPGRADE":
                rollback_source = payload.get("rollback_source")
                rollback_digest = payload.get("rollback_digest")
                rollback_sha = payload.get("rollback_candidate_sha")
                if (
                    payload.get("distribution") != _FACTORY_DISTRIBUTION
                    or payload.get("source") != str(source)
                    or not isinstance(rollback_source, str)
                    or not isinstance(rollback_digest, str)
                    or not isinstance(rollback_sha, str)
                ):
                    raise RuntimeError("Factory package upgrade receipt is invalid")
                rollback_wheel = Path(rollback_source)
                if (
                    rollback_wheel.is_symlink()
                    or not rollback_wheel.is_file()
                    or digest_artifact(rollback_wheel) != rollback_digest
                ):
                    raise RuntimeError("Factory rollback package identity drift")
                self._run_checked(
                    (
                        self._python_executable, "-m", "pip", "install",
                        "--force-reinstall", "--no-deps", "--no-input",
                        str(rollback_wheel),
                    ),
                    "Factory package upgrade rollback",
                )
                observed = self._current_factory_package()
                if (
                    observed is None
                    or observed.candidate_sha != rollback_sha
                    or observed.artifact_digest != rollback_digest
                ):
                    raise RuntimeError("Factory package rollback exact candidate verification failed")
                return
            if payload != {
                "distribution": _FACTORY_DISTRIBUTION,
                "kind": "FACTORY_PACKAGE_INSTALL",
                "source": str(source),
            }:
                raise RuntimeError("Factory package rollback receipt does not match operation")
            self._run_checked(
                (
                    self._python_executable, "-m", "pip", "uninstall", "-y",
                    _FACTORY_DISTRIBUTION,
                ),
                "Factory package rollback",
            )
            return

        if operation.action == "STAGE_FACTORY_SKILL_CATALOG":
            _, target, factory_root, catalog_root, candidate_sha = self._skill_catalog_paths(
                operation,
                target_must_be_absent=False,
            )
            catalog_root_created = payload.get("catalog_root_created")
            factory_root_created = payload.get("factory_root_created")
            if (
                payload.get("kind") != "FACTORY_SKILL_CATALOG_STAGE"
                or payload.get("candidate_sha") != candidate_sha
                or payload.get("target") != str(target)
                or catalog_root_created not in {"true", "false"}
                or factory_root_created not in {"true", "false"}
            ):
                raise RuntimeError("Factory Skill catalog rollback receipt does not match operation")
            if target.is_symlink():
                raise RuntimeError("Factory Skill catalog rollback target became a symlink")
            if target.exists():
                shutil.rmtree(target)
            if catalog_root_created == "true":
                with suppress(OSError):
                    catalog_root.rmdir()
            if factory_root_created == "true":
                with suppress(OSError):
                    factory_root.rmdir()
            return

        if operation.action == "INSTALL_NATIVE_PROFILE_DISTRIBUTION":
            profile_id = self._profile_id(operation)
            if payload.get("kind") == "PROFILE_REUSE":
                if payload != {
                    "kind": "PROFILE_REUSE",
                    "profile_id": profile_id,
                    "source_digest": operation.source_digest or "",
                }:
                    raise RuntimeError("Profile reuse rollback receipt does not match operation")
                return
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

        if operation.action == "ACTIVATE_GATEWAY_FACTORY_RUNTIME":
            started = payload.get("started")
            if payload.get("kind") != "GATEWAY_RUNTIME_ACTIVATE" or started not in {"true", "false"}:
                raise RuntimeError("Gateway activation rollback receipt is invalid")
            if started == "true":
                self._gateway_transition(
                    "stop", running=False, label="Factory Gateway activation rollback"
                )
            return

        if operation.action == "QUIESCE_GATEWAY_FACTORY_RUNTIME":
            was_running = payload.get("was_running")
            if payload.get("kind") != "GATEWAY_RUNTIME_QUIESCE" or was_running not in {"true", "false"}:
                raise RuntimeError("Gateway quiesce rollback receipt is invalid")
            if was_running == "true":
                self._gateway_transition(
                    "restart", running=True, label="Factory Gateway rollback reload"
                )
            self._gateway_was_running = None
            return

        if operation.action == "VERIFY_FACTORY_PLUGIN_SCOPE":
            scope, _, _ = self._factory_plugin_scope(operation)
            if payload != {"kind": "FACTORY_PLUGIN_SCOPE_VERIFIED", "scope": scope}:
                raise RuntimeError("Factory plugin verification rollback receipt is invalid")
            return

        if operation.action == "ACTIVATE_FACTORY_PLUGIN_SCOPE":
            scope, scope_home, profile_prefix = self._factory_plugin_scope(operation)
            snapshot = payload.get("snapshot")
            if (
                payload.get("kind") != "FACTORY_PLUGIN_SCOPE_ACTIVATE"
                or payload.get("scope") != scope
                or not isinstance(snapshot, dict)
            ):
                raise RuntimeError("Factory plugin activation rollback receipt is invalid")
            self._restore_factory_plugin_snapshot(
                scope_home=scope_home,
                profile_prefix=profile_prefix,
                snapshot=snapshot,
                label="Factory plugin activation rollback",
            )
            return

        if operation.action == "REGISTER_FACTORY_PLUGIN_PROFILE":
            profile_id, _, target, plugins_root = self._profile_plugin_paths(
                operation, target_must_be_absent=False
            )
            kind = payload.get("kind")
            if kind == "FACTORY_PLUGIN_PROFILE_REUSE":
                if payload != {
                    "kind": kind,
                    "profile_id": profile_id,
                    "target": str(target),
                }:
                    raise RuntimeError("Factory Profile plugin reuse receipt is invalid")
                return
            if kind == "FACTORY_PLUGIN_PROFILE_UPGRADE":
                backup_raw = payload.get("backup")
                previous_sha = payload.get("previous_candidate_sha")
                if (
                    payload.get("profile_id") != profile_id
                    or payload.get("target") != str(target)
                    or not isinstance(backup_raw, str)
                    or not isinstance(previous_sha, str)
                ):
                    raise RuntimeError("Factory Profile plugin upgrade receipt is invalid")
                backup = Path(backup_raw)
                if backup != self._profile_plugin_backup_path(previous_sha, profile_id):
                    raise RuntimeError("Factory Profile plugin rollback backup identity mismatch")
                if backup.is_symlink() or not backup.is_dir():
                    raise RuntimeError("Factory Profile plugin rollback backup is unavailable")
                if target.is_symlink():
                    raise RuntimeError("Factory Profile plugin rollback target became a symlink")
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(backup, target)
                return
            plugins_root_created = payload.get("plugins_root_created")
            if (
                kind != "FACTORY_PLUGIN_PROFILE_INSTALL"
                or payload.get("profile_id") != profile_id
                or payload.get("target") != str(target)
                or plugins_root_created not in {"true", "false"}
            ):
                raise RuntimeError("Factory Profile plugin rollback receipt does not match operation")
            if target.is_symlink():
                raise RuntimeError("Factory Profile plugin rollback target became a symlink")
            if target.exists():
                shutil.rmtree(target)
            if plugins_root_created == "true":
                with suppress(OSError):
                    plugins_root.rmdir()
            return

        if operation.action == "REGISTER_DASHBOARD_PLUGIN":
            _, target, plugins_root = self._dashboard_paths(
                operation, target_must_be_absent=False
            )
            if payload.get("kind") == "DASHBOARD_PLUGIN_UPGRADE":
                backup_raw = payload.get("backup")
                previous_sha = payload.get("previous_candidate_sha")
                if (
                    payload.get("target") != str(target)
                    or not isinstance(backup_raw, str)
                    or not isinstance(previous_sha, str)
                ):
                    raise RuntimeError("Dashboard upgrade rollback receipt is invalid")
                backup = Path(backup_raw)
                if backup != self._dashboard_backup_path(previous_sha):
                    raise RuntimeError("Dashboard rollback backup identity mismatch")
                if backup.is_symlink() or not backup.is_dir():
                    raise RuntimeError("Dashboard rollback backup is unavailable")
                if target.is_symlink():
                    raise RuntimeError("Dashboard rollback target became a symlink")
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(backup, target)
                return
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

        if operation.action == "VERIFY_NORTHBOUND_CONTROL_BINDING":
            if payload != {"kind": "NORTHBOUND_CONTROL_BINDING_VERIFIED"}:
                raise RuntimeError("northbound control binding receipt does not match operation")
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
                self._restore_kanban_auto_decompose_true(
                    label="Kanban high-assurance rollback"
                )
            return

        if payload != {"kind": "EMPTY_CRON_PLAN"}:
            raise RuntimeError("empty cron rollback receipt does not match operation")
