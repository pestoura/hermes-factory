from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from hermes_factory.compiler.project import EcosystemSnapshot

_CANONICAL_REPOSITORY = "pestoura/hermes-ecosystem-architecture"
_CANONICAL_PATH = "inventory/capabilities.yaml"
_ALLOWED_CLASSIFICATIONS = frozenset(
    {
        "CURRENT",
        "DEPLOYED",
        "IMPLEMENTED_NOT_DEPLOYED",
        "IMPLEMENTED_NOT_ATTESTED",
        "EXPERIMENTAL",
        "PLANNED",
        "BLOCKED",
        "LEGACY",
        "SUPERSEDED",
    }
)


class Hermes360AdapterError(ValueError):
    pass


@dataclass(frozen=True)
class Hermes360Provenance:
    repository: str
    revision: str
    path: str
    blob_sha: str


@dataclass(frozen=True)
class Hermes360Capability:
    capability_id: str
    component: str
    implemented: object
    tested: object
    deployed: object
    production_enabled: object
    planned: bool
    blocked: bool
    classification: str
    evidence: str

    @property
    def compiler_eligible(self) -> bool:
        return (
            self.implemented is True
            and self.tested is True
            and self.planned is False
            and self.blocked is False
        )


@dataclass(frozen=True)
class Hermes360CapabilitySnapshot:
    source: str
    schema_version: int
    observed: str
    provenance: Hermes360Provenance
    capabilities: tuple[Hermes360Capability, ...]
    inventory_digest: str

    def to_compiler_snapshot(self) -> EcosystemSnapshot:
        return EcosystemSnapshot(
            snapshot_id=(
                f"hermes-360:{self.observed}:{self.provenance.revision}"
            ),
            digest=self.inventory_digest,
            capabilities=frozenset(
                capability.capability_id
                for capability in self.capabilities
                if capability.compiler_eligible
            ),
        )


class Hermes360CapabilityAdapter:
    def consume(
        self,
        inventory: dict[str, object],
        *,
        provenance: Hermes360Provenance,
    ) -> Hermes360CapabilitySnapshot:
        self._validate_provenance(provenance)

        schema_version = inventory.get("schema_version")
        if schema_version != 1 or isinstance(schema_version, bool):
            raise Hermes360AdapterError("Hermes 360 schema_version must be exactly 1")

        observed = self._text(inventory.get("observed"), "observed")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed) is None:
            raise Hermes360AdapterError("Hermes 360 observed must be YYYY-MM-DD")

        raw_capabilities = inventory.get("capabilities")
        if not isinstance(raw_capabilities, list):
            raise Hermes360AdapterError("Hermes 360 capabilities must be a list")

        records: list[Hermes360Capability] = []
        seen_ids: set[str] = set()
        for index, raw_record in enumerate(raw_capabilities):
            if not isinstance(raw_record, dict):
                raise Hermes360AdapterError(
                    f"Hermes 360 capability[{index}] must be an object"
                )
            record = self._capability(raw_record, index=index)
            if record.capability_id in seen_ids:
                raise Hermes360AdapterError(
                    f"Hermes 360 duplicate capability id: {record.capability_id}"
                )
            seen_ids.add(record.capability_id)
            records.append(record)

        return Hermes360CapabilitySnapshot(
            source="HERMES_360_CAPABILITY_INVENTORY",
            schema_version=schema_version,
            observed=observed,
            provenance=provenance,
            capabilities=tuple(records),
            inventory_digest=self._digest(inventory, provenance),
        )

    def _capability(
        self,
        record: dict[object, object],
        *,
        index: int,
    ) -> Hermes360Capability:
        capability_id = self._text(record.get("id"), f"capability[{index}].id")
        component = self._text(
            record.get("component"),
            f"capability[{index}].component",
        )
        implemented = self._required_state(
            record,
            "implemented",
            index=index,
        )
        tested = self._required_state(record, "tested", index=index)
        deployed = self._required_state(record, "deployed", index=index)
        production_enabled = self._required_state(
            record,
            "production_enabled",
            index=index,
        )
        planned = self._required_bool(record, "planned", index=index)
        blocked = self._required_bool(record, "blocked", index=index)
        classification = self._text(
            record.get("classification"),
            f"capability[{index}].classification",
        )
        if classification not in _ALLOWED_CLASSIFICATIONS:
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].classification is unknown"
            )
        evidence = self._text(
            record.get("evidence"),
            f"capability[{index}].evidence",
        )
        return Hermes360Capability(
            capability_id=capability_id,
            component=component,
            implemented=implemented,
            tested=tested,
            deployed=deployed,
            production_enabled=production_enabled,
            planned=planned,
            blocked=blocked,
            classification=classification,
            evidence=evidence,
        )

    @staticmethod
    def _required_state(
        record: dict[object, object],
        key: str,
        *,
        index: int,
    ) -> object:
        if key not in record:
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].{key} is required"
            )
        value = record[key]
        if value is not None and not isinstance(value, (bool, str)):
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].{key} must be bool/string/null"
            )
        if isinstance(value, str) and not value.strip():
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].{key} must not be blank"
            )
        return value

    @staticmethod
    def _required_bool(
        record: dict[object, object],
        key: str,
        *,
        index: int,
    ) -> bool:
        if key not in record:
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].{key} is required"
            )
        value = record[key]
        if not isinstance(value, bool):
            raise Hermes360AdapterError(
                f"Hermes 360 capability[{index}].{key} must be boolean"
            )
        return value

    @staticmethod
    def _validate_provenance(provenance: Hermes360Provenance) -> None:
        if provenance.repository != _CANONICAL_REPOSITORY:
            raise Hermes360AdapterError("Hermes 360 repository is not canonical")
        if provenance.path != _CANONICAL_PATH:
            raise Hermes360AdapterError("Hermes 360 inventory path is not canonical")
        Hermes360CapabilityAdapter._sha(provenance.revision, "revision")
        Hermes360CapabilityAdapter._sha(provenance.blob_sha, "blob_sha")

    @staticmethod
    def _sha(value: object, label: str) -> str:
        text = Hermes360CapabilityAdapter._text(value, label)
        if len(text) not in {40, 64} or re.fullmatch(r"[0-9a-fA-F]+", text) is None:
            raise Hermes360AdapterError(
                f"Hermes 360 {label} must be an exact immutable SHA"
            )
        return text.lower()

    @staticmethod
    def _text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise Hermes360AdapterError(
                f"Hermes 360 {label} must be a non-empty string"
            )
        return value.strip()

    @staticmethod
    def _digest(
        inventory: dict[str, object],
        provenance: Hermes360Provenance,
    ) -> str:
        payload = {
            "inventory": inventory,
            "provenance": {
                "repository": provenance.repository,
                "revision": provenance.revision,
                "path": provenance.path,
                "blob_sha": provenance.blob_sha,
            },
        }
        try:
            encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise Hermes360AdapterError(
                "Hermes 360 inventory is not canonically serializable"
            ) from error
        return hashlib.sha256(encoded).hexdigest()
