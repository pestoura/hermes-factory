from pathlib import Path

import yaml

from hermes_factory.runtime.admission import (
    AdmissionEvidenceState,
    RuntimeComponent,
)


ROOT = Path(__file__).parents[2]
BINDING = ROOT / "hermes-integration" / "mcp-bridge" / "factory-northbound.yaml"


def _binding_contract():
    try:
        from hermes_factory.runtime.bindings import (
            ExternalVerificationState,
            RuntimeComponentBinding,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("Phase P external component binding is not implemented") from exc
    return ExternalVerificationState, RuntimeComponentBinding


def test_northbound_bridge_binding_is_exact_sha_and_not_optimistically_passed() -> None:
    verification_state, binding_type = _binding_contract()
    payload = yaml.safe_load(BINDING.read_text(encoding="utf-8"))

    binding = binding_type.from_mapping(payload)

    assert binding.component is RuntimeComponent.NORTHBOUND_CONTROL_INTEGRATION
    assert binding.repository == "pestoura/hermes-mcp-bridge"
    assert binding.pull_request == 111
    assert binding.candidate_sha == "5d96f02ca21b29446e0bf01b06087b353fb45c0b"
    assert binding.verification_state is verification_state.BLOCKED_EXTERNAL_BILLING
    assert binding.admission_state is AdmissionEvidenceState.BLOCKED
    assert binding.to_manifest()["admission_state"] == "BLOCKED"
    assert len(binding.digest) == 64


def test_only_external_pass_can_become_component_pass() -> None:
    verification_state, binding_type = _binding_contract()
    base = {
        "schema": "hermes.factory/runtime-component-binding/v1",
        "component": "NORTHBOUND_CONTROL_INTEGRATION",
        "repository": "pestoura/hermes-mcp-bridge",
        "pull_request": 111,
        "candidate_sha": "a" * 40,
    }

    passed = binding_type.from_mapping(
        {**base, "verification_state": verification_state.PASS.value}
    )
    blocked = binding_type.from_mapping(
        {**base, "verification_state": verification_state.BLOCKED_EXTERNAL_BILLING.value}
    )
    not_run = binding_type.from_mapping(
        {**base, "verification_state": verification_state.NOT_RUN.value}
    )

    assert passed.admission_state is AdmissionEvidenceState.PASS
    assert blocked.admission_state is AdmissionEvidenceState.BLOCKED
    assert not_run.admission_state is AdmissionEvidenceState.NOT_RUN


def test_northbound_binding_declares_safe_mcp_contract() -> None:
    payload = yaml.safe_load(BINDING.read_text(encoding="utf-8"))

    assert payload["default_enabled"] is False
    assert payload["internal_factory_ipc"] is False
    assert payload["mutation_execution"] is False
    assert payload["production_entrypoint"] == "hermes_mcp_bridge.http_runner"
    assert payload["tools"] == [
        "factory_acceptance",
        "factory_evidence",
        "factory_protected_mutation_intent",
        "factory_status",
    ]
    assert payload["protected_actions"] == [
        "ACTIVATE_PROFILE",
        "ACTIVATE_SKILL",
        "MERGE_PR",
        "RELEASE",
    ]
