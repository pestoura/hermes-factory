from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .project import ContractValidationError, _load_mapping, _required


@dataclass(frozen=True)
class EngineeringProfileReference:
    """Immutable identity/digest reference to the canonical JDS profile.

    The Factory intentionally validates only the document identity required to
    bind compilation to JDS input. Capability, delivery, override and gate
    semantics remain owned and validated by JDS itself.
    """

    api_version: str
    kind: str
    standard: str
    platform_ref: str
    criticality: str
    digest: str

    @classmethod
    def from_yaml(cls, path: Path) -> "EngineeringProfileReference":
        raw = _load_mapping(path)
        api_version = _required(
            raw, "apiVersion", expected_type=str, context="engineering"
        )
        if api_version != "engineering.jarvas/v1":
            raise ContractValidationError(
                f"unsupported engineering apiVersion: {api_version}"
            )
        kind = _required(raw, "kind", expected_type=str, context="engineering")
        if kind != "ProjectEngineeringProfile":
            raise ContractValidationError(f"unsupported engineering kind: {kind}")
        spec = _required(raw, "spec", expected_type=dict, context="engineering")
        standard = _required(spec, "standard", expected_type=str, context="engineering.spec")
        platform_ref = _required(
            spec, "platformRef", expected_type=str, context="engineering.spec"
        )
        criticality = _required(
            spec, "criticality", expected_type=str, context="engineering.spec"
        )
        return cls(
            api_version=api_version,
            kind=kind,
            standard=standard,
            platform_ref=platform_ref,
            criticality=criticality,
            digest=_semantic_digest(raw),
        )


def _semantic_digest(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
