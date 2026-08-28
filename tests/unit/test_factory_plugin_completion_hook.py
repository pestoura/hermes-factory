import importlib.util
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
