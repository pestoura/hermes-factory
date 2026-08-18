from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ContractValidationError(ValueError):
    pass


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ContractValidationError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractValidationError("contract root must be a mapping")
    return raw


def _strict_keys(mapping: dict[str, Any], *, allowed: set[str], context: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise ContractValidationError(f"unknown {context} field(s): {sorted(unknown)}")


def _required(mapping: dict[str, Any], key: str, *, expected_type: type, context: str) -> Any:
    if key not in mapping:
        raise ContractValidationError(f"missing {context} field: {key}")
    value = mapping[key]
    if type(value) is not expected_type:
        raise ContractValidationError(f"{context}.{key} must be {expected_type.__name__}")
    if expected_type is str and not value.strip():
        raise ContractValidationError(f"{context}.{key} must not be empty")
    return value


@dataclass(frozen=True)
class ProjectContract:
    project_id: str
    name: str
    repository: str
    autonomy: str

    @classmethod
    def from_yaml(cls, path: Path) -> "ProjectContract":
        raw = _load_mapping(path)
        _strict_keys(raw, allowed={"schema", "project"}, context="top-level")
        schema = _required(raw, "schema", expected_type=str, context="contract")
        if schema != "hermes.factory/project/v1.2":
            raise ContractValidationError(f"unsupported project schema: {schema}")
        project = _required(raw, "project", expected_type=dict, context="contract")
        _strict_keys(project, allowed={"id", "name", "repository", "autonomy"}, context="project")
        return cls(
            project_id=_required(project, "id", expected_type=str, context="project"),
            name=_required(project, "name", expected_type=str, context="project"),
            repository=_required(project, "repository", expected_type=str, context="project"),
            autonomy=_required(project, "autonomy", expected_type=str, context="project"),
        )


@dataclass(frozen=True)
class AcceptanceContract:
    uat_required: bool
    runtime_required: bool
    owner_acceptance_required: bool

    @classmethod
    def from_yaml(cls, path: Path) -> "AcceptanceContract":
        raw = _load_mapping(path)
        _strict_keys(raw, allowed={"schema", "acceptance"}, context="top-level")
        schema = _required(raw, "schema", expected_type=str, context="contract")
        if schema != "hermes.factory/acceptance/v1.2":
            raise ContractValidationError(f"unsupported acceptance schema: {schema}")
        acceptance = _required(raw, "acceptance", expected_type=dict, context="contract")
        _strict_keys(
            acceptance,
            allowed={"uat_required", "runtime_required", "owner_acceptance_required"},
            context="acceptance",
        )
        return cls(
            uat_required=_required(acceptance, "uat_required", expected_type=bool, context="acceptance"),
            runtime_required=_required(acceptance, "runtime_required", expected_type=bool, context="acceptance"),
            owner_acceptance_required=_required(
                acceptance, "owner_acceptance_required", expected_type=bool, context="acceptance"
            ),
        )
