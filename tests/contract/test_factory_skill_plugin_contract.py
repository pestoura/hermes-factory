from pathlib import Path

import yaml

PLUGIN_ROOT = Path("hermes-integration/dashboard-plugin/hermes-factory")


def test_factory_plugin_registers_fail_closed_skill_tool_guard() -> None:
    manifest = yaml.safe_load((PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8"))

    assert manifest["name"] == "hermes-factory"
    assert "pre_tool_call" in manifest["hooks"]

    source = (PLUGIN_ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "guard_factory_skill_tool_call" in source
    assert 'register_hook("pre_tool_call"' in source
    assert "skills_list" in source
    assert "skill_view" in source


def test_factory_plugin_registers_durable_completion_handoff_hook() -> None:
    manifest = yaml.safe_load((PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    assert "kanban_task_completed" in manifest["hooks"]

    source = (PLUGIN_ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "build_installed_completion_coordinator" in source
    assert "_on_kanban_task_completed" in source
    assert 'register_hook("kanban_task_completed"' in source
    assert "factory:handoff-blocked/v1" in source
