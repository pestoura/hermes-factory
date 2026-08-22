from pathlib import Path

import yaml

COMPONENT_MAP = Path("hermes-integration/install/component-map.yaml")


SUPPORTED = {
    "FACTORY_PACKAGE",
    "FACTORY_SKILLS",
    "PROFILE_DISTRIBUTIONS",
    "KANBAN_HIGH_ASSURANCE_POLICY",
    "NATIVE_PROFILE_CRON",
    "DASHBOARD_PLUGIN",
    "GATEWAY_HITL_ADAPTER",
    "NORTHBOUND_CONTROL_INTEGRATION",
}

BLOCKED: dict[str, str] = {}


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


def test_northbound_component_declares_verification_not_registration():
    document = yaml.safe_load(COMPONENT_MAP.read_text(encoding="utf-8"))
    northbound = document["components"]["NORTHBOUND_CONTROL_INTEGRATION"]

    assert northbound["mechanism"] == "verify_existing_hermes_mcp_bridge_northbound_binding"
    assert northbound["source"] == "hermes-integration/mcp-bridge/factory-northbound.yaml"
    assert northbound["target"] == "HERMES_MCP_BRIDGE"
