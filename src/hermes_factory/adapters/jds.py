from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from hermes_factory.contracts import EngineeringProfileReference


class JDSAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class JDSEffectiveGatePlan:
    source: str
    schema: str
    standard: str
    platform_ref: str
    criticality: str
    change_source: str
    ambiguous_impact: bool
    effective_capabilities: tuple[str, ...]
    selected_capabilities: tuple[str, ...]
    selected_gates: tuple[str, ...]
    skipped_capabilities: dict[str, str]
    plan_digest: str


class JDSGatePlanAdapter:
    def consume(
        self,
        plan: dict[str, object],
        *,
        profile: EngineeringProfileReference,
    ) -> JDSEffectiveGatePlan:
        schema = self._required_str(plan, "schema")
        if schema != "engineering.jarvas/gate-plan-v1":
            raise JDSAdapterError(f"unsupported JDS gate-plan schema: {schema}")

        standard = self._required_str(plan, "standard")
        if standard != profile.standard:
            raise JDSAdapterError(
                f"JDS standard does not match engineering profile: {standard}"
            )

        platform_ref = self._required_str(plan, "platformRef")
        if platform_ref != profile.platform_ref:
            raise JDSAdapterError("JDS platformRef does not match engineering profile")

        criticality = self._required_str(plan, "criticality")
        if criticality != profile.criticality:
            raise JDSAdapterError("JDS criticality does not match engineering profile")

        change_source = self._required_str(plan, "changeSource")
        ambiguous_impact = plan.get("ambiguousImpact")
        if not isinstance(ambiguous_impact, bool):
            raise JDSAdapterError("JDS ambiguousImpact must be boolean")

        effective = self._required_unique_str_list(plan, "effectiveCapabilities")
        selected = self._required_unique_str_list(plan, "selectedCapabilities")
        gates = self._required_unique_str_list(plan, "selectedGates")
        skipped = self._required_str_mapping(plan, "skippedCapabilities")

        if not set(selected).issubset(effective):
            raise JDSAdapterError(
                "JDS selectedCapabilities must be contained in effectiveCapabilities"
            )

        return JDSEffectiveGatePlan(
            source="JDS_EFFECTIVE_GATE_PLAN",
            schema=schema,
            standard=standard,
            platform_ref=platform_ref,
            criticality=criticality,
            change_source=change_source,
            ambiguous_impact=ambiguous_impact,
            effective_capabilities=effective,
            selected_capabilities=selected,
            selected_gates=gates,
            skipped_capabilities=skipped,
            plan_digest=self._semantic_digest(plan),
        )

    @staticmethod
    def _required_str(plan: dict[str, object], key: str) -> str:
        value = plan.get(key)
        if not isinstance(value, str) or not value.strip():
            raise JDSAdapterError(f"JDS {key} must be a non-empty string")
        return value

    @staticmethod
    def _required_unique_str_list(
        plan: dict[str, object],
        key: str,
    ) -> tuple[str, ...]:
        value = plan.get(key)
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise JDSAdapterError(f"JDS {key} must be a list of non-empty strings")
        items = tuple(value)
        if len(set(items)) != len(items):
            raise JDSAdapterError(f"JDS {key} must not contain duplicates")
        return items

    @staticmethod
    def _required_str_mapping(plan: dict[str, object], key: str) -> dict[str, str]:
        value = plan.get(key)
        if not isinstance(value, dict) or any(
            not isinstance(item_key, str)
            or not item_key.strip()
            or not isinstance(item_value, str)
            or not item_value.strip()
            for item_key, item_value in value.items()
        ):
            raise JDSAdapterError(f"JDS {key} must be a string mapping")
        return {str(item_key): str(item_value) for item_key, item_value in value.items()}

    @staticmethod
    def _semantic_digest(plan: dict[str, object]) -> str:
        try:
            encoded = json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise JDSAdapterError("JDS gate plan is not canonically serializable") from error
        return hashlib.sha256(encoded).hexdigest()
