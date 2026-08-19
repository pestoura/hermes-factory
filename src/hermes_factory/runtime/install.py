from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hermes_factory.gates.exact_sha import ExactSHAState, evaluate_exact_sha
from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.admission import AdmissionEvidenceState, RuntimeComponent
from hermes_factory.runtime.cron_projection import NativeCronPlan
from hermes_factory.runtime.readiness import RuntimeReadinessAssessor


class InstallPlanError(ValueError):
    pass


_SECRET_PATH_PARTS = {
    ".env",
    "secrets",
    "secret",
    "tokens",
    "token",
    "credentials",
    "credential",
}
_MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass(frozen=True)
class InstallOperation:
    component: RuntimeComponent
    action: str
    argv: tuple[str, ...] = ()
    source: str | None = None
    target: str | None = None

    def to_manifest(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "component": self.component.value,
            "action": self.action,
            "argv": list(self.argv),
        }
        if self.source is not None:
            payload["source"] = self.source
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(frozen=True)
class ControlledInstallPlan:
    accepted_hermes_sha: str
    observed_hermes_sha: str
    operations: tuple[InstallOperation, ...]
    blockers: tuple[str, ...]
    execution_state: str
    ready_for_controlled_execution: bool
    execute: bool

    def to_manifest(self) -> dict[str, object]:
        return {
            "schema": "hermes.factory/controlled-install-plan/v1",
            "accepted_hermes_sha": self.accepted_hermes_sha,
            "observed_hermes_sha": self.observed_hermes_sha,
            "operations": [operation.to_manifest() for operation in self.operations],
            "blockers": list(self.blockers),
            "execution_state": self.execution_state,
            "ready_for_controlled_execution": self.ready_for_controlled_execution,
            "execute": self.execute,
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_manifest(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _reject_secret_like_path(path: Path, label: str) -> None:
    parts = {part.lower() for part in path.parts}
    if parts & _SECRET_PATH_PARTS:
        raise InstallPlanError(f"{label} contains secret-like path material")


def _require_regular_file(path: Path, label: str) -> None:
    _reject_secret_like_path(path, label)
    if path.is_symlink() or not path.is_file():
        raise InstallPlanError(f"{label} must be an existing regular file")


def _require_directory(path: Path, label: str) -> None:
    _reject_secret_like_path(path, label)
    if path.is_symlink() or not path.is_dir():
        raise InstallPlanError(f"{label} must be an existing directory")


class ControlledInstallPlanBuilder:
    def build(
        self,
        *,
        accepted_hermes_sha: str,
        observed_hermes_sha: str,
        factory_package_source: Path,
        expected_factory_package_digest: str,
        profile_artifacts: Mapping[str, Path],
        expected_profile_digests: Mapping[str, str],
        profile_eval_states: Mapping[str, AdmissionEvidenceState],
        skill_eval_states: Mapping[str, AdmissionEvidenceState],
        component_states: Mapping[RuntimeComponent, AdmissionEvidenceState],
        cron_plan: NativeCronPlan,
        dashboard_plugin_source: Path,
        gateway_adapter_module: str,
        northbound_binding_source: Path,
    ) -> ControlledInstallPlan:
        factory_package_source = Path(factory_package_source)
        dashboard_plugin_source = Path(dashboard_plugin_source)
        northbound_binding_source = Path(northbound_binding_source)
        _require_regular_file(factory_package_source, "Factory package source")
        _require_directory(dashboard_plugin_source, "dashboard plugin source")
        _require_regular_file(
            dashboard_plugin_source / "dashboard" / "manifest.json",
            "dashboard plugin manifest",
        )
        _require_regular_file(northbound_binding_source, "northbound binding source")
        if not _MODULE_NAME.fullmatch(gateway_adapter_module):
            raise InstallPlanError("gateway adapter module is invalid")

        blockers: list[str] = []
        sha_state = evaluate_exact_sha(accepted_hermes_sha, (observed_hermes_sha,))
        if sha_state is not ExactSHAState.SHA_MATCH:
            blockers.append(
                f"exact Hermes SHA required: accepted={accepted_hermes_sha} observed={observed_hermes_sha}"
            )

        observed_package_digest = digest_artifact(factory_package_source)
        if observed_package_digest != expected_factory_package_digest:
            blockers.append(
                "Factory package digest drift: "
                f"expected={expected_factory_package_digest} observed={observed_package_digest}"
            )

        profile_ids = tuple(sorted(profile_artifacts))
        expected_ids = set(expected_profile_digests)
        actual_ids = set(profile_artifacts)
        if expected_ids != actual_ids:
            missing = sorted(expected_ids - actual_ids)
            unexpected = sorted(actual_ids - expected_ids)
            blockers.append(
                f"Profile artifact identity mismatch: missing={missing} unexpected={unexpected}"
            )

        for profile_id in profile_ids:
            artifact = Path(profile_artifacts[profile_id])
            _require_directory(artifact, f"Profile artifact {profile_id}")
            expected_digest = expected_profile_digests.get(profile_id)
            if expected_digest is None:
                continue
            observed_digest = digest_artifact(artifact)
            if observed_digest != expected_digest:
                blockers.append(
                    f"Profile {profile_id} digest drift: expected={expected_digest} observed={observed_digest}"
                )

        readiness = RuntimeReadinessAssessor().assess(
            required_profile_ids=profile_ids,
            required_skill_ids=tuple(sorted(skill_eval_states)),
            profile_eval_states=profile_eval_states,
            skill_eval_states=skill_eval_states,
            component_states=component_states,
        )
        blockers.extend(readiness.blockers)

        if cron_plan.execution_state == "BLOCKED":
            blockers.append("Native Profile cron plan is BLOCKED")

        operations: list[InstallOperation] = [
            InstallOperation(
                component=RuntimeComponent.FACTORY_PACKAGE,
                action="STAGE_FACTORY_PACKAGE",
                source=str(factory_package_source),
                target="HERMES_RUNTIME_ENV",
            )
        ]
        for profile_id in profile_ids:
            artifact = Path(profile_artifacts[profile_id])
            operations.append(
                InstallOperation(
                    component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
                    action="INSTALL_NATIVE_PROFILE_DISTRIBUTION",
                    argv=("hermes", "profile", "install", str(artifact)),
                    source=str(artifact),
                    target=f"HERMES_HOME/profiles/{profile_id}",
                )
            )

        operations.extend(
            [
                InstallOperation(
                    component=RuntimeComponent.FACTORY_SKILLS,
                    action="INSTALL_FACTORY_SKILLS_WITH_PROFILE_DISTRIBUTIONS",
                    source="canonical factory-* Skill artifacts",
                    target="PROFILE_SCOPED_SKILLS",
                ),
                InstallOperation(
                    component=RuntimeComponent.KANBAN_HIGH_ASSURANCE_POLICY,
                    action="APPLY_NATIVE_KANBAN_HIGH_ASSURANCE_POLICY",
                    target="HERMES_KANBAN",
                ),
            ]
        )

        if cron_plan.commands:
            for command in cron_plan.commands:
                operations.append(
                    InstallOperation(
                        component=RuntimeComponent.NATIVE_PROFILE_CRON,
                        action="CREATE_NATIVE_PROFILE_CRON_DUTY",
                        argv=command.argv,
                        target=f"HERMES_PROFILE/{command.profile_id}/cron",
                    )
                )
        else:
            operations.append(
                InstallOperation(
                    component=RuntimeComponent.NATIVE_PROFILE_CRON,
                    action="APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
                    target="HERMES_PROFILE_CRON",
                )
            )

        operations.extend(
            [
                InstallOperation(
                    component=RuntimeComponent.DASHBOARD_PLUGIN,
                    action="REGISTER_DASHBOARD_PLUGIN",
                    source=str(dashboard_plugin_source),
                    target="HERMES_HOME/plugins/hermes-factory",
                ),
                InstallOperation(
                    component=RuntimeComponent.GATEWAY_HITL_ADAPTER,
                    action="REGISTER_GATEWAY_HITL_ADAPTER",
                    source=gateway_adapter_module,
                    target="HERMES_GATEWAY",
                ),
                InstallOperation(
                    component=RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION,
                    action="REGISTER_NORTHBOUND_CONTROL_INTEGRATION",
                    source=str(northbound_binding_source),
                    target="HERMES_MCP_BRIDGE",
                ),
            ]
        )

        ordered_blockers = tuple(dict.fromkeys(blockers))
        ready = not ordered_blockers
        return ControlledInstallPlan(
            accepted_hermes_sha=accepted_hermes_sha,
            observed_hermes_sha=observed_hermes_sha,
            operations=tuple(operations),
            blockers=ordered_blockers,
            execution_state="READY" if ready else "BLOCKED",
            ready_for_controlled_execution=ready,
            execute=False,
        )
