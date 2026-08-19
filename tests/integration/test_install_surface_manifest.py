from pathlib import Path

import yaml

from hermes_factory.runtime.admission import RuntimeComponent

ROOT = Path(__file__).resolve().parents[2]
INSTALL_SURFACE = ROOT / "hermes-integration/install/component-map.yaml"


def test_install_surface_declares_all_phase_p_components_and_never_executes_by_default():
    payload = yaml.safe_load(INSTALL_SURFACE.read_text(encoding="utf-8"))

    assert payload["schema"] == "hermes.factory/install-surface/v1"
    assert payload["execute"] is False
    assert payload["runtime_state"] == "NOT_RUN"
    assert payload["requires"]["exact_hermes_sha"] is True
    assert payload["requires"]["exact_factory_candidate_sha"] is True
    assert payload["requires"]["verified_factory_package_candidate_v2"] is True
    assert payload["requires"]["all_profile_evals_pass"] is True
    assert payload["requires"]["all_skill_evals_pass"] is True
    assert payload["requires"]["all_component_evidence_pass"] is True
    assert payload["prohibitions"] == [
        "embedded_secrets",
        "embedded_memories",
        "embedded_sessions",
        "embedded_runtime_state",
        "internal_mcp_ipc",
        "implicit_execution",
        "mutable_factory_package_source",
    ]

    components = payload["components"]
    assert set(components) == {component.value for component in RuntimeComponent}
    assert components["FACTORY_PACKAGE"]["mechanism"] == "install_verified_factory_wheel"
    assert components["FACTORY_PACKAGE"]["source"] == (
        "verified_exact_head_factory_package_candidate"
    )
    assert components["PROFILE_DISTRIBUTIONS"]["mechanism"] == "hermes profile install"
    assert components["FACTORY_SKILLS"]["mechanism"] == "profile_scoped_native_skill_directories"
    assert components["NATIVE_PROFILE_CRON"]["mechanism"] == "hermes -p PROFILE cron create"
    assert components["DASHBOARD_PLUGIN"]["source"] == (
        "hermes-integration/dashboard-plugin/hermes-factory"
    )
    assert components["GATEWAY_HITL_ADAPTER"]["source"] == (
        "hermes_factory.adapters.hermes_gateway"
    )
    assert components["NORTHBOUND_CONTROL_INTEGRATION"]["source"] == (
        "hermes-integration/mcp-bridge/factory-northbound.yaml"
    )
