from __future__ import annotations

from typing import Any


class RuntimePolicyProjectionError(ValueError):
    pass


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimePolicyProjectionError(f"{label} must be a mapping")
    return value


def project_native_profile_config(
    agent: dict[str, Any],
    runtime_policies: dict[str, Any],
) -> dict[str, Any]:
    if runtime_policies.get("status") != "approved_for_implementation":
        raise RuntimePolicyProjectionError("runtime policy is not approved for implementation")
    if runtime_policies.get("implementation_authority") != "GRANTED":
        raise RuntimePolicyProjectionError("runtime policy implementation authority is not granted")

    model_class = agent.get("model_class")
    model_classes = _require_mapping(runtime_policies.get("model_classes"), "model_classes")
    model_policy = model_classes.get(model_class)
    if not isinstance(model_class, str) or not isinstance(model_policy, dict):
        raise RuntimePolicyProjectionError(f"unknown model class {model_class!r}")
    if model_policy.get("selection") != "factory-model-policy":
        raise RuntimePolicyProjectionError(
            f"model class {model_class} does not delegate selection to factory-model-policy"
        )

    tool_policy_class = agent.get("tool_policy_class")
    tool_policies = _require_mapping(
        runtime_policies.get("tool_policy_classes"), "tool_policy_classes"
    )
    tool_policy = tool_policies.get(tool_policy_class)
    if not isinstance(tool_policy_class, str) or not isinstance(tool_policy, dict):
        raise RuntimePolicyProjectionError(f"unknown tool policy {tool_policy_class!r}")

    toolsets = tool_policy.get("hermes_toolsets")
    if not isinstance(toolsets, list) or not all(
        isinstance(toolset, str) and toolset.strip() for toolset in toolsets
    ):
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} requires explicit Hermes toolsets"
        )
    if len(toolsets) != len(set(toolsets)):
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} contains duplicate Hermes toolsets"
        )

    mcp = tool_policy.get("mcp")
    if mcp != []:
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} cannot project internal MCP dependencies"
        )

    terminal_policy = tool_policy.get("terminal")
    terminal_enabled = "terminal" in toolsets
    if terminal_policy == "disabled" and terminal_enabled:
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} disables terminal but enables terminal toolset"
        )
    if terminal_policy not in {"disabled", "disabled-by-default"} and not terminal_enabled:
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} requires terminal semantics without terminal toolset"
        )

    browser_policy = tool_policy.get("browser")
    if browser_policy == "disabled" and "browser" in toolsets:
        raise RuntimePolicyProjectionError(
            f"tool policy {tool_policy_class} disables browser but enables browser toolset"
        )

    defaults = _require_mapping(
        runtime_policies.get("hermes_profile_defaults"), "hermes_profile_defaults"
    )
    home_mode = defaults.get("home_mode")
    if home_mode not in {"auto", "real", "profile"}:
        raise RuntimePolicyProjectionError("Hermes profile home_mode is invalid")
    for invariant in (
        "secrets_in_distribution",
        "memories_in_distribution",
        "sessions_in_distribution",
        "runtime_state_in_distribution",
    ):
        if defaults.get(invariant) != "forbidden":
            raise RuntimePolicyProjectionError(
                f"runtime policy must keep {invariant} forbidden"
            )

    return {
        "toolsets": list(toolsets),
        "terminal": {"home_mode": home_mode},
    }
