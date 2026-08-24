import ast
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
    assert payload["requires"]["verified_factory_skill_catalog_candidate_v1"] is True
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
        "mutable_factory_skill_source",
        "worker_skill_self_expansion",
    ]

    components = payload["components"]
    assert set(components) == {component.value for component in RuntimeComponent}
    assert components["FACTORY_PACKAGE"]["mechanism"] == "install_verified_factory_wheel"
    assert components["FACTORY_PACKAGE"]["source"] == (
        "verified_exact_head_factory_package_candidate"
    )
    assert components["PROFILE_DISTRIBUTIONS"]["mechanism"] == "hermes profile install"
    assert components["FACTORY_SKILLS"]["mechanism"] == (
        "exact_head_private_catalog_plus_task_scoped_native_projection"
    )
    assert components["FACTORY_SKILLS"]["source"] == (
        "verified_exact_head_factory_skill_catalog_candidate"
    )
    assert components["FACTORY_SKILLS"]["runtime_adapter_status"] == "SUPPORTED"
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


def test_factory_plugin_manifest_declares_every_registered_hook():
    plugin_root = ROOT / "hermes-integration/dashboard-plugin/hermes-factory"
    manifest = yaml.safe_load((plugin_root / "plugin.yaml").read_text(encoding="utf-8"))
    module = ast.parse((plugin_root / "__init__.py").read_text(encoding="utf-8"))

    register_fn = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "register"
    )
    registered = []
    for node in ast.walk(register_fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "register_hook" or not node.args:
            continue
        hook = node.args[0]
        if isinstance(hook, ast.Constant) and isinstance(hook.value, str):
            registered.append(hook.value)

    assert manifest["hooks"] == registered
