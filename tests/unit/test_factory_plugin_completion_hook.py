import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

PLUGIN = Path("hermes-integration/dashboard-plugin/hermes-factory/__init__.py")


def _load_plugin():
    spec = importlib.util.spec_from_file_location("factory_plugin_test", PLUGIN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCoordinator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def on_task_completed(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("handoff proof missing")
        return ()


def test_non_factory_completion_is_ignored_before_runtime_builder(monkeypatch) -> None:
    plugin = _load_plugin()
    built = []
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(idempotency_key=None),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator",
        lambda: built.append(True),
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="misc")

    assert built == []


def test_factory_completion_invokes_installed_coordinator(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeCoordinator()
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key="factory:jarvas-cli:WP-A:SPECIFY:" + "a" * 64
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator", lambda: coordinator,
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="jarvas-cli")

    assert coordinator.calls == [{"task_id": "t_1", "board": "jarvas-cli"}]


def test_factory_handoff_failure_records_blocked_diagnostic_without_raising(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeCoordinator(fail=True)
    recorded = []
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key="factory:jarvas-cli:WP-A:SPECIFY:" + "a" * 64
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_completion_coordinator", lambda: coordinator,
    )
    monkeypatch.setattr(
        plugin, "_record_handoff_blocked", lambda **kwargs: recorded.append(kwargs),
    )

    plugin._on_kanban_task_completed(task_id="t_1", board="jarvas-cli")

    assert coordinator.calls == [{"task_id": "t_1", "board": "jarvas-cli"}]
    assert len(recorded) == 1
    assert recorded[0]["board"] == "jarvas-cli"
    assert recorded[0]["task_id"] == "t_1"
    assert str(recorded[0]["error"]) == "handoff proof missing"


def _factory_metadata(revision: str, finding_state: str = "NONE") -> dict:
    return {
        "factory_handoff": {
            "schema": "hermes.factory/handoff-completion/v1",
            "stage_outcome": "PASS",
            "artifact_refs": ["artifact:requirements"],
            "evidence_refs": ["evidence:spec"],
            "evidence_states": ["PASS"],
            "finding_state": finding_state,
            "context_revision": revision,
            "candidate_identity": None,
            "independent_review_state": None,
        }
    }


def test_factory_complete_with_open_findings_is_blocked_before_tool(monkeypatch) -> None:
    plugin = _load_plugin()
    revision = "4" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"
            ),
        ),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": _factory_metadata(revision, "OPEN")},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "finding_state" in result["message"]


def test_factory_complete_with_ready_handoff_is_allowed(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setattr(
        plugin, "validate_factory_repository_precompletion", lambda **kwargs: "a" * 40
    )
    revision = "5" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"
            ),
        ),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": _factory_metadata(revision)},
    )

    assert result is None


def test_factory_complete_with_dirty_repository_is_blocked_before_tool(monkeypatch) -> None:
    plugin = _load_plugin()
    revision = "6" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    task = SimpleNamespace(
        assignee="factory-tdd-red",
        workspace_path="/repo/.worktrees/t_1",
        idempotency_key=(
            f"factory:jarvas-cli:WP-A:TDD_RED:{revision}.stage-contract-v7"
        ),
    )
    monkeypatch.setattr(plugin, "_load_native_task", lambda task_id, board=None: task)

    def reject_repository(**kwargs):
        raise plugin.InstalledRuntimeBindingError("candidate worktree is dirty")

    monkeypatch.setattr(
        plugin, "validate_factory_repository_precompletion", reject_repository, raising=False
    )
    metadata = _factory_metadata(revision)
    metadata["factory_handoff"]["candidate_identity"] = "a" * 40

    result = plugin._on_pre_tool_call(
        tool_name="kanban_complete",
        args={"task_id": "t_1", "metadata": metadata},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "worktree is dirty" in result["message"]


class FakeReworkCoordinator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def schedule(self, **kwargs):
        self.calls.append(("schedule", kwargs))
        if self.fail:
            raise RuntimeError("producer_stage must identify exactly one direct parent stage")
        return "t_rework"

    def activate_pending(self, **kwargs):
        self.calls.append(("activate", kwargs))
        if self.fail:
            raise RuntimeError("pending rework activation failed")
        return "t_rework"


def _rework_reason() -> str:
    return (
        '[factory:upstream-rework/v1] '
        '{"producer_stage":"TDD_RED","finding":"contradictory RED tests",'
        '"evidence_refs":["tests/test_cli_core.py"]}'
    )


def test_factory_dependency_block_schedules_upstream_rework_before_native_block(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "a" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is None
    assert len(coordinator.calls) == 1
    assert coordinator.calls[0][0] == "schedule"
    assert coordinator.calls[0][1]["board"] == "jarvas-cli"
    assert coordinator.calls[0][1]["consumer_task_id"] == "t_impl"
    assert coordinator.calls[0][1]["request"].producer_stage == "TDD_RED"


def test_factory_upstream_rework_requires_dependency_block_kind(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "b" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "capability", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "kind=dependency" in result["message"]
    assert coordinator.calls == []


def test_factory_upstream_rework_schedule_failure_keeps_worker_in_flight(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator(fail=True)
    revision = "c" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "upstream rework validation failed" in result["message"]


def test_rework_completion_relies_on_native_dependency_recompute(monkeypatch) -> None:
    plugin = _load_plugin()
    built = []
    revision = "d" * 64
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            idempotency_key=(
                "factory:jarvas-cli:WP-A~rework-tdd_red-r7-deadbeef1234:"
                f"TDD_RED:{revision}.stage-contract-v10"
            )
        ),
    )
    monkeypatch.setattr(
        plugin,
        "build_installed_completion_coordinator",
        lambda: built.append(True),
    )

    plugin._on_kanban_task_completed(task_id="t_rework", board="jarvas-cli")

    assert built == []


def test_factory_post_block_activates_prepared_rework(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    plugin._on_post_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_impl", "kind": "dependency", "reason": _rework_reason()},
        result='{"task_id":"t_impl","run_id":7}',
    )

    assert coordinator.calls[0][0] == "activate"
    assert coordinator.calls[0][1]["board"] == "jarvas-cli"
    assert coordinator.calls[0][1]["consumer_task_id"] == "t_impl"
    assert coordinator.calls[0][1]["request"].producer_stage == "TDD_RED"


def test_factory_upstream_rework_rejects_mismatched_task_context(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "e" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={"task_id": "t_other", "kind": "dependency", "reason": _rework_reason()},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "task_id" in result["message"]
    assert coordinator.calls == []


def test_factory_upstream_rework_rejects_mismatched_board_context(monkeypatch) -> None:
    plugin = _load_plugin()
    coordinator = FakeReworkCoordinator()
    revision = "f" * 64
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_impl")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-engineer",
            idempotency_key=(
                f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v10"
            ),
        ),
    )
    monkeypatch.setattr(
        plugin, "build_installed_upstream_rework_coordinator", lambda: coordinator,
        raising=False,
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_block",
        args={
            "task_id": "t_impl",
            "board": "other-board",
            "kind": "dependency",
            "reason": _rework_reason(),
        },
    )

    assert result is not None
    assert result["action"] == "block"
    assert "board" in result["message"]
    assert coordinator.calls == []

def _factory_v13_terminal_task(workspace: str):
    return SimpleNamespace(
        assignee="factory-requirements-engineer",
        workspace_path=workspace,
        idempotency_key=(
            "factory:jarvas-cli:WP-A:DISCOVER:" + "a" * 64 + ".stage-contract-v13"
        ),
    )


def test_v13_factory_terminal_blocks_global_git_history(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_discover")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _factory_v13_terminal_task(str(tmp_path)),
    )

    result = plugin._on_pre_tool_call(
        tool_name="terminal",
        args={
            "command": "git log --oneline --all -- docs/factory/WP-A/DISCOVER/requirements.md",
            "workdir": str(tmp_path),
        },
    )

    assert result is not None
    assert result["action"] == "block"
    assert "canonical Git read boundary" in result["message"]


def test_v13_factory_terminal_blocks_non_head_history_object(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "factory@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Factory Test"], check=True)
    (repo / "baseline.md").write_text("baseline\n")
    subprocess.run(["git", "-C", str(repo), "add", "baseline.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "baseline"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "superseded"], check=True)
    (repo / "old.md").write_text("superseded\n")
    subprocess.run(["git", "-C", str(repo), "add", "old.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "superseded"], check=True)
    old_sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"], check=True)

    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_discover")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _factory_v13_terminal_task(str(repo)),
    )

    result = plugin._on_pre_tool_call(
        tool_name="terminal",
        args={"command": f"git show {old_sha}:old.md", "workdir": str(repo)},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "not reachable from current HEAD" in result["message"]



def _make_diverged_history_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "history-repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "factory@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Factory Test"], check=True)
    (repo / "baseline.md").write_text("baseline\n")
    subprocess.run(["git", "-C", str(repo), "add", "baseline.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "baseline"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "superseded"], check=True)
    (repo / "old.md").write_text("superseded\n")
    subprocess.run(["git", "-C", str(repo), "add", "old.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "superseded"], check=True)
    old_sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"], check=True)
    return repo, old_sha


def _run_v13_terminal_guard(monkeypatch, repo: Path, command: str):
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_discover")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _factory_v13_terminal_task(str(repo)),
    )
    return plugin._on_pre_tool_call(
        tool_name="terminal", args={"command": command, "workdir": str(repo)}
    )


def test_v13_factory_terminal_checks_every_git_invocation(monkeypatch, tmp_path: Path) -> None:
    repo, old_sha = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(
        monkeypatch, repo, f"git status --short && git show {old_sha}:old.md"
    )
    assert result is not None
    assert result["action"] == "block"
    assert "not reachable from current HEAD" in result["message"]


def test_v13_factory_terminal_blocks_git_object_redirection(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "GIT_DIR=/tmp/other git status")
    assert result is not None
    assert result["action"] == "block"
    assert "Git repository redirection" in result["message"]


def test_v13_factory_terminal_blocks_git_c_outside_workspace(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git -C /tmp log --oneline HEAD")
    assert result is not None
    assert result["action"] == "block"
    assert "outside assigned worktree" in result["message"]


def test_v13_factory_terminal_blocks_cat_file_of_non_head_object(monkeypatch, tmp_path: Path) -> None:
    repo, old_sha = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, f"git cat-file -p {old_sha}")
    assert result is not None
    assert result["action"] == "block"
    assert "not reachable from current HEAD" in result["message"]


def test_v13_factory_terminal_blocks_log_of_non_head_history(monkeypatch, tmp_path: Path) -> None:
    repo, old_sha = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, f"git log --oneline {old_sha}")
    assert result is not None
    assert result["action"] == "block"
    assert "not reachable from current HEAD" in result["message"]


def test_v13_factory_terminal_blocks_switch_to_superseded_ref(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git switch superseded")
    assert result is not None
    assert result["action"] == "block"
    assert "change canonical HEAD lineage" in result["message"]


def test_v13_factory_terminal_blocks_checkout_to_superseded_ref(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git checkout superseded")
    assert result is not None
    assert result["action"] == "block"
    assert "change canonical HEAD lineage" in result["message"]


def test_v13_factory_terminal_blocks_restore_from_superseded_ref(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git restore --source=superseded old.md")
    assert result is not None
    assert result["action"] == "block"
    assert "non-HEAD restore source" in result["message"]


def test_v13_factory_terminal_allows_current_head_and_ancestor_reads(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result_head = _run_v13_terminal_guard(monkeypatch, repo, "git show HEAD:baseline.md")
    result_ancestor = _run_v13_terminal_guard(monkeypatch, repo, "git log --oneline HEAD~0")
    result_status = _run_v13_terminal_guard(monkeypatch, repo, "git status --short")
    assert result_head is None
    assert result_ancestor is None
    assert result_status is None


def test_v13_factory_terminal_blocks_branch_enumeration_but_allows_current_branch(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    blocked = _run_v13_terminal_guard(monkeypatch, repo, "git branch")
    allowed = _run_v13_terminal_guard(monkeypatch, repo, "git branch --show-current")
    assert blocked is not None
    assert blocked["action"] == "block"
    assert "ref/object enumeration" in blocked["message"]
    assert allowed is None


def test_v13_factory_terminal_blocks_other_history_readers(monkeypatch, tmp_path: Path) -> None:
    repo, old_sha = _make_diverged_history_repo(tmp_path)
    commands = (
        f"git diff {old_sha} -- baseline.md",
        f"git grep superseded {old_sha} -- old.md",
        f"git archive {old_sha}",
        f"git blame {old_sha} -- baseline.md",
    )
    for command in commands:
        result = _run_v13_terminal_guard(monkeypatch, repo, command)
        assert result is not None, command
        assert result["action"] == "block"
        assert "not reachable from current HEAD" in result["message"]


def test_v13_factory_terminal_blocks_batch_object_reads(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git cat-file --batch")
    assert result is not None
    assert result["action"] == "block"
    assert "streamed revision input" in result["message"]


def test_v13_factory_terminal_blocks_unknown_git_aliases(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git historical-artifact")
    assert result is not None
    assert result["action"] == "block"
    assert "unsupported Git subcommand" in result["message"]


def test_v13_factory_terminal_blocks_commit_amend_but_allows_normal_stage_git(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    blocked = _run_v13_terminal_guard(monkeypatch, repo, "git commit --amend --no-edit")
    assert blocked is not None
    assert blocked["action"] == "block"
    assert "rewrite prior commits" in blocked["message"]
    for command in ("git diff", "git add baseline.md", "git commit -m stage-checkpoint"):
        assert _run_v13_terminal_guard(monkeypatch, repo, command) is None


def test_v13_factory_terminal_uses_hook_task_id_when_env_task_is_absent(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin()
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _factory_v13_terminal_task(str(tmp_path)),
    )
    result = plugin._on_pre_tool_call(
        tool_name="terminal",
        task_id="t_discover",
        args={"command": "git log --all", "workdir": str(tmp_path)},
    )
    assert result is not None
    assert result["action"] == "block"
    assert "canonical Git read boundary" in result["message"]


def test_v13_factory_terminal_blocks_attached_ref_enumeration_selectors(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    for command in (
        "git log --branches=superseded --oneline",
        "git rev-parse --glob=refs/heads/*",
        "git log --tags --oneline",
    ):
        result = _run_v13_terminal_guard(monkeypatch, repo, command)
        assert result is not None, command
        assert result["action"] == "block"
        assert "global history enumeration" in result["message"]


def test_v13_factory_terminal_blocks_per_invocation_git_config(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git -c color.ui=false status")
    assert result is not None
    assert result["action"] == "block"
    assert "per-invocation Git config" in result["message"]


def test_v13_factory_terminal_blocks_commit_message_reuse_from_history(monkeypatch, tmp_path: Path) -> None:
    repo, old_sha = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, f"git commit -C {old_sha}")
    assert result is not None
    assert result["action"] == "block"
    assert "historical commit reuse" in result["message"]


def test_v13_factory_terminal_blocks_remote_archive(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git archive --remote=/tmp/other HEAD")
    assert result is not None
    assert result["action"] == "block"
    assert "remote archive" in result["message"]

def test_v13_factory_terminal_allows_plain_diff_path(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git diff baseline.md")
    assert result is None


def test_v13_factory_terminal_allows_plain_blame_path(monkeypatch, tmp_path: Path) -> None:
    repo, _ = _make_diverged_history_repo(tmp_path)
    result = _run_v13_terminal_guard(monkeypatch, repo, "git blame baseline.md")
    assert result is None



def _factory_v14_context_task() -> SimpleNamespace:
    return SimpleNamespace(
        assignee="factory-requirements-engineer",
        idempotency_key=(
            "factory:jarvas-cli:WP-A:DISCOVER:" + "a" * 64 + ".stage-contract-v14"
        ),
    )


def _kanban_show_with_cross_generation_role_history() -> str:
    worker_context = """# Kanban task t_current: WP-A/DISCOVER

## Body
current task body

## Parent task results
### t_parent
current-generation parent handoff

## Recent work by @factory-requirements-engineer
- t_superseded — old DISCOVER: Baselined 17 requirements
- t_older — old SPECIFY: ADR-0019

## Comment thread
comment from worker `factory-orchestrator`:
current-generation comment
"""
    return json.dumps(
        {
            "task": {
                "id": "t_current",
                "title": "WP-A/DISCOVER",
                "assignee": "factory-requirements-engineer",
                "body": "Use generation-scoped worker context only; current approved task.",
            },
            "parents": ["t_parent"],
            "children": ["t_child"],
            "comments": [{"author": "factory-orchestrator", "body": "current-generation comment"}],
            "events": [],
            "runs": [{"id": 99, "status": "running"}],
            "worker_context": worker_context,
        }
    )


def test_v14_factory_kanban_show_removes_cross_generation_role_history(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )
    original = _kanban_show_with_cross_generation_role_history()
    callback = getattr(plugin, "_on_transform_tool_result", lambda **kwargs: None)

    transformed = callback(
        tool_name="kanban_show",
        args={},
        result=original,
        task_id="t_current",
    )
    payload = json.loads(transformed if isinstance(transformed, str) else original)
    context = payload["worker_context"]

    assert "## Recent work by @factory-requirements-engineer" not in context
    assert "t_superseded" not in context
    assert "t_older" not in context
    assert "## Parent task results" in context
    assert "t_parent" in context
    assert "current-generation parent handoff" in context
    assert "## Comment thread" in context
    assert "current-generation comment" in context


def test_v13_factory_kanban_show_keeps_legacy_worker_context(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key=(
                "factory:jarvas-cli:WP-A:DISCOVER:" + "a" * 64 + ".stage-contract-v13"
            ),
        ),
    )
    original = _kanban_show_with_cross_generation_role_history()
    callback = getattr(plugin, "_on_transform_tool_result", lambda **kwargs: None)

    transformed = callback(
        tool_name="kanban_show", args={}, result=original, task_id="t_current"
    )

    assert transformed is None


def test_v14_factory_kanban_show_blocks_cross_task_reads(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_show",
        args={"task_id": "t_superseded"},
        task_id="t_current",
    )

    assert result is not None
    assert result["action"] == "block"
    assert "cross-task" in result["message"]


def test_v14_worker_context_preserves_body_heading_that_looks_like_role_history(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )
    body_marker = "## Recent work by @literal-in-approved-body"
    generated_marker = "## Recent work by @factory-requirements-engineer"
    payload = json.loads(_kanban_show_with_cross_generation_role_history())
    payload["worker_context"] = payload["worker_context"].replace(
        "current task body",
        "current task body\n" + body_marker + "\napproved canonical body text",
    )

    transformed = plugin._on_transform_tool_result(
        tool_name="kanban_show",
        args={},
        result=json.dumps(payload),
        task_id="t_current",
    )
    assert isinstance(transformed, str)
    context = json.loads(transformed)["worker_context"]
    assert body_marker in context
    assert "approved canonical body text" in context
    assert generated_marker not in context
    assert "t_superseded" not in context



def test_v14_worker_context_removes_generated_history_even_when_comment_spoofs_heading(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )
    payload = json.loads(_kanban_show_with_cross_generation_role_history())
    payload["worker_context"] = payload["worker_context"].replace(
        "current-generation comment",
        "current-generation comment\n"
        "## Recent work by @factory-requirements-engineer\n"
        "- t_comment_spoof — comment content",
    )

    transformed = plugin._on_transform_tool_result(
        tool_name="kanban_show",
        args={},
        result=json.dumps(payload),
        task_id="t_current",
    )
    assert isinstance(transformed, str)
    context = json.loads(transformed)["worker_context"]
    assert "t_superseded" not in context
    assert "t_older" not in context


def test_v14_factory_kanban_show_blocks_cross_board_reads(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_show",
        args={"task_id": "t_current", "board": "other-board"},
        task_id="t_current",
    )

    assert result is not None
    assert result["action"] == "block"
    assert "board" in result["message"]


def test_v14_transform_fails_closed_on_cross_task_result(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )
    payload = json.loads(_kanban_show_with_cross_generation_role_history())
    payload["task"]["id"] = "t_superseded"
    payload["task"]["title"] = "superseded task"

    transformed = plugin._on_transform_tool_result(
        tool_name="kanban_show",
        args={},
        result=json.dumps(payload),
        task_id="t_current",
    )

    assert isinstance(transformed, str)
    sanitized = json.loads(transformed)
    assert "error" in sanitized
    assert "cross-task" in sanitized["error"]
    assert "task" not in sanitized


def test_v14_transform_uses_result_contract_when_native_lookup_fails(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")

    def _fail_lookup(task_id, board=None):
        raise RuntimeError("transient native lookup failure")

    monkeypatch.setattr(plugin, "_load_native_task", _fail_lookup)
    original = _kanban_show_with_cross_generation_role_history()

    transformed = plugin._on_transform_tool_result(
        tool_name="kanban_show",
        args={},
        result=original,
        task_id="t_current",
    )

    assert isinstance(transformed, str)
    context = json.loads(transformed)["worker_context"]
    assert "t_superseded" not in context
    assert "t_older" not in context



def test_v14_transform_blocks_malformed_kanban_show_result(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v14_context_task(),
    )

    transformed = plugin._on_transform_tool_result(
        tool_name="kanban_show",
        args={},
        result='{"task":',
        task_id="t_current",
    )

    assert isinstance(transformed, str)
    payload = json.loads(transformed)
    assert "error" in payload
    assert "malformed" in payload["error"]


def _factory_v15_workspace_task(workspace: Path) -> SimpleNamespace:
    return SimpleNamespace(
        assignee="factory-requirements-engineer",
        idempotency_key=(
            "factory:jarvas-cli:WP-A:DISCOVER:" + "a" * 64 + ".stage-contract-v15"
        ),
        workspace_path=str(workspace),
    )


def _run_v15_workspace_guard(monkeypatch, workspace: Path, tool_name: str, args: dict):
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v15_workspace_task(workspace),
    )
    return plugin._on_pre_tool_call(tool_name=tool_name, args=args, task_id="t_current")


def test_v15_terminal_blocks_parent_repository_read(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "jarvas-cli"
    workspace = repo / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)

    result = _run_v15_workspace_guard(
        monkeypatch,
        workspace,
        "terminal",
        {"command": f"ls -la {repo}", "workdir": str(workspace)},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "workspace read boundary" in result["message"]


def test_v15_terminal_blocks_relative_workspace_escape(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "terminal", {"command": "cat ../../../secret.md"}
    )
    assert result is not None
    assert result["action"] == "block"


def test_v15_read_file_blocks_parent_repository(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "jarvas-cli"
    workspace = repo / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "read_file", {"path": str(repo / "docs" / "legacy.md")}
    )
    assert result is not None
    assert result["action"] == "block"
    assert "workspace read boundary" in result["message"]


def test_v15_search_files_blocks_parent_repository(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "jarvas-cli"
    workspace = repo / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "search_files", {"pattern": "ADR", "path": str(repo)}
    )
    assert result is not None
    assert result["action"] == "block"


def test_v15_workspace_local_reads_remain_allowed(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    assert _run_v15_workspace_guard(
        monkeypatch, workspace, "read_file", {"path": str(workspace / "README.md")}
    ) is None
    assert _run_v15_workspace_guard(
        monkeypatch, workspace, "terminal", {"command": "cat README.md"}
    ) is None


def test_v14_workspace_read_boundary_is_backward_compatible(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-requirements-engineer",
            idempotency_key="factory:p:WP-A:DISCOVER:" + "a" * 64 + ".stage-contract-v14",
            workspace_path=str(workspace),
        ),
    )
    assert plugin._on_pre_tool_call(
        tool_name="read_file", args={"path": str(workspace.parent.parent)}, task_id="t_current"
    ) is None


def test_v15_terminal_blocks_cd_parent_escape(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "terminal", {"command": "cd .. && cat sibling.txt"}
    )
    assert result is not None
    assert result["action"] == "block"


def test_v15_read_file_blocks_symlink_escape(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    outside = tmp_path / "outside"
    workspace.mkdir(parents=True)
    outside.mkdir()
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "read_file", {"path": str(workspace / "escape" / "secret.md")}
    )
    assert result is not None
    assert result["action"] == "block"


def test_v15_terminal_blocks_embedded_absolute_path(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    target = repo / "secret.txt"
    result = _run_v15_workspace_guard(
        monkeypatch,
        workspace,
        "terminal",
        {"command": f'''python -c "open('{target}').read()"'''},
    )
    assert result is not None
    assert result["action"] == "block"


def test_v15_terminal_blocks_home_expansion(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v15_workspace_guard(
        monkeypatch, workspace, "terminal", {"command": "cat $HOME/.config/private"}
    )
    assert result is not None
    assert result["action"] == "block"


def _factory_v18_workspace_task(workspace: Path) -> SimpleNamespace:
    return SimpleNamespace(
        assignee="factory-software-architect",
        idempotency_key=(
            "factory:jarvas-cli:WP-A:DESIGN:" + "a" * 64 + ".stage-contract-v18"
        ),
        workspace_path=str(workspace),
    )


def _run_v18_stage_write_guard(monkeypatch, workspace: Path, tool_name: str, args: dict):
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: _factory_v18_workspace_task(workspace),
    )
    return plugin._on_pre_tool_call(tool_name=tool_name, args=args, task_id="t_current")


def test_v18_write_file_blocks_oversized_stage_payload(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v18_stage_write_guard(
        monkeypatch,
        workspace,
        "write_file",
        {"path": str(workspace / "docs" / "evidence.md"), "content": "x" * 8001},
    )
    assert result is not None
    assert result["action"] == "block"
    assert "8000" in result["message"]
    assert "bounded" in result["message"]


def test_v18_write_file_allows_bounded_stage_payload(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v18_stage_write_guard(
        monkeypatch,
        workspace,
        "write_file",
        {"path": str(workspace / "docs" / "evidence.md"), "content": "x" * 8000},
    )
    assert result is None


def test_v18_patch_blocks_aggregate_oversized_stage_payload(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v18_stage_write_guard(
        monkeypatch,
        workspace,
        "patch",
        {
            "mode": "replace",
            "path": str(workspace / "docs" / "evidence.md"),
            "old_string": "x" * 4001,
            "new_string": "y" * 4000,
        },
    )
    assert result is not None
    assert result["action"] == "block"
    assert "8000" in result["message"]


def test_v18_patch_blocks_oversized_stage_payload(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    result = _run_v18_stage_write_guard(
        monkeypatch,
        workspace,
        "patch",
        {
            "mode": "replace",
            "path": str(workspace / "docs" / "evidence.md"),
            "old_string": "tail",
            "new_string": "tail" + "x" * 8001,
        },
    )
    assert result is not None
    assert result["action"] == "block"
    assert "8000" in result["message"]


def test_v17_write_file_remains_backward_compatible(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "repo" / ".worktrees" / "t_current"
    workspace.mkdir(parents=True)
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin,
        "_load_native_task",
        lambda task_id, board=None: SimpleNamespace(
            assignee="factory-software-architect",
            idempotency_key=(
                "factory:jarvas-cli:WP-A:DESIGN:" + "a" * 64 + ".stage-contract-v17"
            ),
            workspace_path=str(workspace),
        ),
    )
    assert plugin._on_pre_tool_call(
        tool_name="write_file",
        args={"path": str(workspace / "docs" / "legacy.md"), "content": "x" * 8001},
        task_id="t_current",
    ) is None


def _review_guard_task(*, stage: str, version: int):
    revision = "b" * 64
    return SimpleNamespace(
        assignee="factory-code-reviewer",
        idempotency_key=(
            f"factory:jarvas-cli:WP-A:{stage}:{revision}.stage-contract-v{version}"
        ),
    )


def test_v20_factory_review_stage_blocks_native_review_request(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "jarvas-cli")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _review_guard_task(stage="CODE_REVIEW", version=20),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_request_review",
        args={"task_id": "t_current", "summary": "review complete"},
        task_id="t_current",
    )

    assert result is not None
    assert result["action"] == "block"
    assert "already the independent reviewer" in result["message"]
    assert "kanban_complete" in result["message"]
    assert "independent_review_state=PASS" in result["message"]


def test_v20_non_review_factory_stage_keeps_native_review_request_behavior(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _review_guard_task(stage="IMPLEMENT", version=20),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_request_review",
        args={"task_id": "t_current", "summary": "manual review workflow"},
        task_id="t_current",
    )

    assert result is None


def test_v19_review_stage_remains_backward_compatible_for_native_review_request(monkeypatch) -> None:
    plugin = _load_plugin()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_current")
    monkeypatch.setattr(
        plugin, "_load_native_task",
        lambda task_id, board=None: _review_guard_task(stage="CODE_REVIEW", version=19),
    )

    result = plugin._on_pre_tool_call(
        tool_name="kanban_request_review",
        args={"task_id": "t_current", "summary": "legacy behavior"},
        task_id="t_current",
    )

    assert result is None
