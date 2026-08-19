import pytest


def _projection_contract():
    try:
        from hermes_factory.agents.runtime_projection import (
            RuntimePolicyProjectionError,
            project_native_profile_config,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("native runtime policy projection is not implemented") from exc
    return RuntimePolicyProjectionError, project_native_profile_config


def _policies():
    return {
        "status": "approved_for_implementation",
        "implementation_authority": "GRANTED",
        "model_classes": {
            "reasoning-high": {"selection": "factory-model-policy"},
        },
        "tool_policy_classes": {
            "review": {
                "hermes_toolsets": ["terminal", "file", "web", "skills", "todo", "kanban"],
                "mcp": [],
                "terminal": "sandboxed-readonly-candidate",
                "browser": "disabled",
            },
            "control-read": {
                "hermes_toolsets": ["skills", "todo", "kanban"],
                "mcp": [],
                "terminal": "disabled",
                "browser": "disabled",
            },
        },
        "hermes_profile_defaults": {
            "home_mode": "profile",
            "secrets_in_distribution": "forbidden",
            "memories_in_distribution": "forbidden",
            "sessions_in_distribution": "forbidden",
            "runtime_state_in_distribution": "forbidden",
        },
    }


def test_runtime_policy_projects_only_native_hermes_config() -> None:
    _, project = _projection_contract()
    config = project(
        {"model_class": "reasoning-high", "tool_policy_class": "review"},
        _policies(),
    )

    assert config == {
        "toolsets": ["terminal", "file", "web", "skills", "todo", "kanban"],
        "terminal": {"home_mode": "profile"},
    }
    assert "model_class" not in config
    assert "tool_policy_class" not in config
    assert "factory_agent_id" not in config
    assert "model" not in config


def test_runtime_policy_requires_approved_implementation_authority() -> None:
    error_type, project = _projection_contract()
    policies = _policies()
    policies["implementation_authority"] = "NOT_GRANTED"

    with pytest.raises(error_type, match="implementation authority"):
        project(
            {"model_class": "reasoning-high", "tool_policy_class": "review"},
            policies,
        )


def test_runtime_policy_fails_closed_on_unknown_model_or_tool_policy() -> None:
    error_type, project = _projection_contract()

    with pytest.raises(error_type, match="model class"):
        project(
            {"model_class": "unknown", "tool_policy_class": "review"},
            _policies(),
        )
    with pytest.raises(error_type, match="tool policy"):
        project(
            {"model_class": "reasoning-high", "tool_policy_class": "unknown"},
            _policies(),
        )


def test_runtime_policy_rejects_internal_mcp_and_toolset_policy_contradictions() -> None:
    error_type, project = _projection_contract()
    policies = _policies()
    policies["tool_policy_classes"]["review"]["mcp"] = ["internal-factory"]
    with pytest.raises(error_type, match="MCP"):
        project(
            {"model_class": "reasoning-high", "tool_policy_class": "review"},
            policies,
        )

    policies = _policies()
    policies["tool_policy_classes"]["control-read"]["hermes_toolsets"] = [
        "terminal",
        "skills",
        "todo",
        "kanban",
    ]
    with pytest.raises(error_type, match="terminal"):
        project(
            {"model_class": "reasoning-high", "tool_policy_class": "control-read"},
            policies,
        )
