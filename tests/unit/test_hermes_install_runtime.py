import json
from pathlib import Path

import pytest

from hermes_factory.runtime.admission import RuntimeComponent
from hermes_factory.runtime.install import InstallOperation


def _contract():
    try:
        from hermes_factory.runtime.hermes_install_runtime import (
            CommandResult,
            HermesJarvasInstallRuntime,
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("Hermes/Jarvas install runtime adapter is not implemented") from exc
    return CommandResult, HermesJarvasInstallRuntime


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, argv):
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError("unexpected command execution")
        return self.responses.pop(0)


def test_runtime_preflight_rejects_unsupported_operation_before_any_command(tmp_path: Path):
    result_type, runtime_type = _contract()
    runner = FakeRunner([result_type(0, "", "")])
    runtime = runtime_type(command_runner=runner)
    unsupported = InstallOperation(
        component=RuntimeComponent.FACTORY_SKILLS,
        action="INSTALL_FACTORY_SKILLS_WITH_PROFILE_DISTRIBUTIONS",
        target="PROFILE_SCOPED_SKILLS",
    )

    with pytest.raises(RuntimeError, match="unsupported install operation"):
        runtime.preflight((unsupported,))

    assert runner.calls == []


def test_runtime_applies_and_rolls_back_native_profile_install(tmp_path: Path):
    result_type, runtime_type = _contract()
    profile = tmp_path / "factory-orchestrator"
    profile.mkdir()
    (profile / "distribution.yaml").write_text("name: factory-orchestrator\n", encoding="utf-8")
    operation = InstallOperation(
        component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
        action="INSTALL_NATIVE_PROFILE_DISTRIBUTION",
        argv=(
            "hermes",
            "profile",
            "install",
            str(profile),
            "--name",
            "factory-orchestrator",
            "-y",
        ),
        source=str(profile),
        target="HERMES_HOME/profiles/factory-orchestrator",
    )
    runner = FakeRunner(
        [
            result_type(0, "Profile installed: factory-orchestrator\n", ""),
            result_type(0, "Deleted profile: factory-orchestrator\n", ""),
        ]
    )
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload["kind"] == "PROFILE_INSTALL"
    assert payload["profile_id"] == "factory-orchestrator"

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        operation.argv,
        ("hermes", "profile", "delete", "factory-orchestrator", "-y"),
    ]


def test_runtime_applies_and_rolls_back_native_profile_cron(tmp_path: Path):
    result_type, runtime_type = _contract()
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="CREATE_NATIVE_PROFILE_CRON_DUTY",
        argv=(
            "hermes",
            "-p",
            "factory-release-manager",
            "cron",
            "create",
            "0 9 * * 1",
            "Run release review",
            "--name",
            "weekly-release-review",
        ),
        target="HERMES_PROFILE/factory-release-manager/cron",
    )
    runner = FakeRunner(
        [
            result_type(
                0,
                "Created job: job-123\n  Name: weekly-release-review\n",
                "",
            ),
            result_type(0, "Removed job: job-123\n", ""),
        ]
    )
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload == {
        "job_id": "job-123",
        "kind": "PROFILE_CRON_CREATE",
        "profile_id": "factory-release-manager",
    }

    runtime.rollback(operation, receipt)
    assert runner.calls == [
        operation.argv,
        ("hermes", "-p", "factory-release-manager", "cron", "remove", "job-123"),
    ]


def test_runtime_fails_if_cron_success_output_has_no_job_id():
    result_type, runtime_type = _contract()
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="CREATE_NATIVE_PROFILE_CRON_DUTY",
        argv=(
            "hermes",
            "-p",
            "factory-release-manager",
            "cron",
            "create",
            "0 9 * * 1",
            "Run release review",
            "--name",
            "weekly-release-review",
        ),
        target="HERMES_PROFILE/factory-release-manager/cron",
    )
    runner = FakeRunner([result_type(0, "Created successfully\n", "")])
    runtime = runtime_type(command_runner=runner)

    runtime.preflight((operation,))
    with pytest.raises(RuntimeError, match="job id"):
        runtime.apply(operation)


def test_runtime_empty_cron_plan_is_explicit_noop_with_no_command():
    _, runtime_type = _contract()
    runner = FakeRunner([])
    runtime = runtime_type(command_runner=runner)
    operation = InstallOperation(
        component=RuntimeComponent.NATIVE_PROFILE_CRON,
        action="APPLY_EMPTY_NATIVE_PROFILE_CRON_PLAN",
        target="HERMES_PROFILE_CRON",
    )

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt) == {"kind": "EMPTY_CRON_PLAN"}
    runtime.rollback(operation, receipt)
    assert runner.calls == []


def test_runtime_applies_and_rolls_back_dashboard_plugin_without_overwrite(tmp_path: Path):
    _, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    source = tmp_path / "dashboard-plugin" / "hermes-factory"
    (source / "dashboard" / "dist").mkdir(parents=True)
    (source / "dashboard" / "manifest.json").write_text(
        '{"name":"hermes-factory","entry":"dist/index.js"}\n', encoding="utf-8"
    )
    (source / "dashboard" / "dist" / "index.js").write_text("plugin();\n", encoding="utf-8")
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="REGISTER_DASHBOARD_PLUGIN",
        source=str(source),
        target="HERMES_HOME/plugins/hermes-factory",
    )
    runner = FakeRunner([])
    runtime = runtime_type(command_runner=runner, hermes_home=hermes_home)

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    target = hermes_home / "plugins" / "hermes-factory"
    assert (target / "dashboard" / "manifest.json").is_file()
    assert json.loads(receipt)["kind"] == "DASHBOARD_PLUGIN_INSTALL"

    runtime.rollback(operation, receipt)
    assert not target.exists()
    assert runner.calls == []


def test_runtime_dashboard_preflight_refuses_existing_plugin_target(tmp_path: Path):
    _, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    target = hermes_home / "plugins" / "hermes-factory"
    target.mkdir(parents=True)
    source = tmp_path / "source"
    (source / "dashboard").mkdir(parents=True)
    (source / "dashboard" / "manifest.json").write_text("{}\n", encoding="utf-8")
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="REGISTER_DASHBOARD_PLUGIN",
        source=str(source),
        target="HERMES_HOME/plugins/hermes-factory",
    )
    runtime = runtime_type(command_runner=FakeRunner([]), hermes_home=hermes_home)

    with pytest.raises(RuntimeError, match="already exists"):
        runtime.preflight((operation,))



def _factory_plugin_source(tmp_path: Path) -> Path:
    source = tmp_path / "dashboard-plugin" / "hermes-factory"
    (source / "dashboard").mkdir(parents=True)
    (source / "plugin.yaml").write_text(
        "name: hermes-factory\nhooks:\n  - pre_tool_call\n  - kanban_task_completed\n",
        encoding="utf-8",
    )
    (source / "dashboard" / "manifest.json").write_text(
        '{"name":"hermes-factory","entry":"dist/index.js"}\n', encoding="utf-8"
    )
    return source


def test_runtime_projects_factory_plugin_into_profile_scope_and_rolls_back(tmp_path: Path):
    _, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    profile_home = hermes_home / "profiles" / "factory-orchestrator"
    profile_home.mkdir(parents=True)
    source = _factory_plugin_source(tmp_path)
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="REGISTER_FACTORY_PLUGIN_PROFILE",
        source=str(source),
        target="HERMES_HOME/profiles/factory-orchestrator/plugins/hermes-factory",
    )
    runner = FakeRunner([])
    runtime = runtime_type(command_runner=runner, hermes_home=hermes_home)
    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    target = profile_home / "plugins" / "hermes-factory"
    assert (target / "plugin.yaml").is_file()
    assert json.loads(receipt)["kind"] == "FACTORY_PLUGIN_PROFILE_INSTALL"
    runtime.rollback(operation, receipt)
    assert not target.exists()
    assert runner.calls == []


def test_runtime_activates_factory_plugin_scope_with_native_cli_and_restores_previous_config(tmp_path: Path):
    result_type, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "plugins:\n  enabled: [other]\n  disabled: [hermes-factory, blocked]\n"
        "  entries:\n    hermes-factory:\n      allow_tool_override: true\n",
        encoding="utf-8",
    )
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="ACTIVATE_FACTORY_PLUGIN_SCOPE",
        argv=("hermes", "plugins", "enable", "hermes-factory", "--no-allow-tool-override"),
        target="HERMES_HOME",
    )
    runner = FakeRunner([
        result_type(0, "enabled\n", ""),
        result_type(0, '["hermes-factory","other"]\n', ""),
        result_type(0, 'false\n', ""),
        result_type(0, "restored enabled\n", ""),
        result_type(0, "restored disabled\n", ""),
        result_type(0, "restored entry\n", ""),
    ])
    runtime = runtime_type(command_runner=runner, hermes_home=hermes_home)
    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload["kind"] == "FACTORY_PLUGIN_SCOPE_ACTIVATE"
    assert payload["scope"] == "HERMES_HOME"
    runtime.rollback(operation, receipt)
    assert runner.calls == [
        operation.argv,
        ("hermes", "config", "get", "plugins.enabled", "--json"),
        ("hermes", "config", "get", "plugins.entries.hermes-factory.allow_tool_override", "--json"),
        ("hermes", "config", "set", "plugins.enabled", '["other"]'),
        ("hermes", "config", "set", "plugins.disabled", '["hermes-factory","blocked"]'),
        ("hermes", "config", "set", "plugins.entries.hermes-factory", '{"allow_tool_override":true}'),
    ]


def test_runtime_verifies_factory_plugin_callbacks_in_profile_scope(tmp_path: Path):
    result_type, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    profile_home = hermes_home / "profiles" / "factory-orchestrator"
    profile_home.mkdir(parents=True)
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="VERIFY_FACTORY_PLUGIN_SCOPE",
        target="HERMES_HOME/profiles/factory-orchestrator",
    )
    runner = FakeRunner([result_type(0, "", "")])
    runtime = runtime_type(
        command_runner=runner,
        hermes_home=hermes_home,
        python_executable="/opt/hermes/venv/bin/python",
    )
    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    assert json.loads(receipt) == {
        "kind": "FACTORY_PLUGIN_SCOPE_VERIFIED",
        "scope": "HERMES_HOME/profiles/factory-orchestrator",
    }
    argv = runner.calls[0]
    assert argv[:3] == (
        "env",
        f"HERMES_HOME={profile_home}",
        "/opt/hermes/venv/bin/python",
    )
    assert argv[3] == "-c"
    compile(argv[4], "<factory-plugin-probe>", "exec")
    expected_runtime_root = Path("/opt/hermes/venv/bin/python").parent.parent.parent
    assert f"os.chdir({json.dumps(str(expected_runtime_root))})" in argv[4]
    assert 'has_hook("pre_tool_call")' in argv[4]
    assert 'has_hook("post_tool_call")' in argv[4]
    assert 'has_hook("transform_tool_result")' in argv[4]
    assert 'has_hook("kanban_task_completed")' in argv[4]
    assert 'list_plugins()' in argv[4]
    assert 'hermes-factory' in argv[4]



def test_runtime_plugin_verification_surfaces_bounded_loader_diagnostic(tmp_path: Path):
    result_type, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    operation = InstallOperation(
        component=RuntimeComponent.DASHBOARD_PLUGIN,
        action="VERIFY_FACTORY_PLUGIN_SCOPE",
        target="HERMES_HOME",
    )
    runner = FakeRunner([
        result_type(
            1,
            "",
            "Failed to load plugin 'hermes-factory': synthetic loader diagnostic",
        )
    ])
    runtime = runtime_type(
        command_runner=runner,
        hermes_home=hermes_home,
        python_executable="/opt/hermes/venv/bin/python",
    )
    runtime.preflight((operation,))
    with pytest.raises(RuntimeError, match="synthetic loader diagnostic"):
        runtime.apply(operation)


def test_runtime_enforces_and_rolls_back_canonical_profile_inference_identity(tmp_path: Path) -> None:
    result_type, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    profile_home = hermes_home / "profiles" / "factory-orchestrator"
    profile_home.mkdir(parents=True)
    (profile_home / "config.yaml").write_text(
        "toolsets: [terminal, kanban]\n"
        "plugins:\n"
        "  enabled: [hermes-factory]\n",
        encoding="utf-8",
    )
    operation = InstallOperation(
        component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
        action="ENFORCE_FACTORY_PROFILE_INFERENCE_IDENTITY",
        target="HERMES_HOME/profiles/factory-orchestrator",
    )
    hermes = "/opt/hermes/venv/bin/hermes"
    runner = FakeRunner([
        result_type(0, "set default\n", ""),
        result_type(0, "set provider\n", ""),
        result_type(0, "set base url\n", ""),
        result_type(0, '"tencent/hy3:free"\n', ""),
        result_type(0, '"nous"\n', ""),
        result_type(0, '"https://inference-api.nousresearch.com/v1"\n', ""),
        result_type(0, "unset default\n", ""),
        result_type(0, "unset provider\n", ""),
        result_type(0, "unset base url\n", ""),
    ])
    runtime = runtime_type(
        command_runner=runner,
        hermes_home=hermes_home,
        python_executable="/opt/hermes/venv/bin/python",
    )

    runtime.preflight((operation,))
    receipt = runtime.apply(operation)
    payload = json.loads(receipt)
    assert payload["kind"] == "FACTORY_PROFILE_INFERENCE_IDENTITY"
    assert payload["profile_id"] == "factory-orchestrator"
    assert payload["model"] == "tencent/hy3:free"
    assert payload["provider"] == "nous"

    runtime.rollback(operation, receipt)
    prefix = (hermes, "-p", "factory-orchestrator", "config")
    assert runner.calls == [
        (*prefix, "set", "model.default", "tencent/hy3:free"),
        (*prefix, "set", "model.provider", "nous"),
        (*prefix, "set", "model.base_url", "https://inference-api.nousresearch.com/v1"),
        (*prefix, "get", "model.default", "--json"),
        (*prefix, "get", "model.provider", "--json"),
        (*prefix, "get", "model.base_url", "--json"),
        (*prefix, "unset", "model.default"),
        (*prefix, "unset", "model.provider"),
        (*prefix, "unset", "model.base_url"),
    ]


def test_runtime_profile_inference_verification_failure_compensates_before_raising(tmp_path: Path) -> None:
    result_type, runtime_type = _contract()
    hermes_home = tmp_path / "hermes-home"
    profile_home = hermes_home / "profiles" / "factory-orchestrator"
    profile_home.mkdir(parents=True)
    (profile_home / "config.yaml").write_text("toolsets: [terminal]\n", encoding="utf-8")
    operation = InstallOperation(
        component=RuntimeComponent.PROFILE_DISTRIBUTIONS,
        action="ENFORCE_FACTORY_PROFILE_INFERENCE_IDENTITY",
        target="HERMES_HOME/profiles/factory-orchestrator",
    )
    runner = FakeRunner([
        result_type(0, "", ""),
        result_type(0, "", ""),
        result_type(0, "", ""),
        result_type(0, '"tencent/hy3:free"\n', ""),
        result_type(0, '"nvidia"\n', ""),
        result_type(0, "", ""),
        result_type(0, "", ""),
        result_type(0, "", ""),
    ])
    runtime = runtime_type(
        command_runner=runner,
        hermes_home=hermes_home,
        python_executable="/opt/hermes/venv/bin/python",
    )

    runtime.preflight((operation,))
    with pytest.raises(RuntimeError, match="verification failed for model.provider"):
        runtime.apply(operation)

    hermes = "/opt/hermes/venv/bin/hermes"
    prefix = (hermes, "-p", "factory-orchestrator", "config")
    assert runner.calls[-3:] == [
        (*prefix, "unset", "model.default"),
        (*prefix, "unset", "model.provider"),
        (*prefix, "unset", "model.base_url"),
    ]
