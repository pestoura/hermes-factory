from pathlib import Path

import yaml

COMPONENT_MAP = Path("hermes-integration/install/component-map.yaml")


SUPPORTED = {
    "FACTORY_PACKAGE",
    "PROFILE_DISTRIBUTIONS",
    "NATIVE_PROFILE_CRON",
    "DASHBOARD_PLUGIN",
}

BLOCKED = {
    "FACTORY_SKILLS": "STRUCTURAL_DECISION_REQUIRED",
    "KANBAN_HIGH_ASSURANCE_POLICY": "UPSTREAM_CAPABILITY_GAP",
    "GATEWAY_HITL_ADAPTER": "RUNTIME_BINDING_MISSING",
    "NORTHBOUND_CONTROL_INTEGRATION": "EXTERNAL_CI_BLOCKED",
}


def test_install_component_map_distinguishes_concrete_runtime_support_from_blockers():
    document = yaml.safe_load(COMPONENT_MAP.read_text(encoding="utf-8"))
    components = document["components"]

    assert set(components) == SUPPORTED | set(BLOCKED)

    for component in SUPPORTED:
        assert components[component]["runtime_adapter_status"] == "SUPPORTED"
        assert "blocker_code" not in components[component]

    for component, blocker_code in BLOCKED.items():
        assert components[component]["runtime_adapter_status"] == "BLOCKED"
        assert components[component]["blocker_code"] == blocker_code

    assert document["runtime_state"] == "NOT_RUN"
    assert document["execute"] is False
