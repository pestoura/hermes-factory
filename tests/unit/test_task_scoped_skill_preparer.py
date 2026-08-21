from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from hermes_factory.governance.candidate_identity import digest_artifact
from hermes_factory.runtime.hermes_install_runtime import CommandResult
from hermes_factory.runtime.task_skills import HermesTaskSkillPreparer
from hermes_factory.skills.system import SkillAdmissionError, SkillRegistry


@dataclass
class FakeTask:
    assignee: str
    skills: tuple[str, ...]
    workspace_kind: str


class FakeNativeTaskRuntime:
    def __init__(self, task: FakeTask, workspace: Path) -> None:
        self.task = task
        self.workspace = workspace
        self.calls: list[tuple[str, object]] = []

    @contextmanager
    def connect_closing(self, *, board: str):
        self.calls.append(("connect_closing", board))
        yield object()

    def get_task(self, conn: object, task_id: str) -> FakeTask | None:
        self.calls.append(("get_task", task_id))
        return self.task

    def resolve_workspace(self, task: FakeTask, *, board: str) -> str:
        self.calls.append(("resolve_workspace", board))
        self.workspace.mkdir(parents=True, exist_ok=True)
        return str(self.workspace)


class FakeRunner:
    def __init__(self, responses: list[CommandResult]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(tuple(argv))
        if not self.responses:
            raise AssertionError("unexpected command execution")
        return self.responses.pop(0)


def _registry() -> SkillRegistry:
    return SkillRegistry(
        aliases={},
        registered=frozenset(
            {
                "factory-tdd-implementation",
                "factory-cli-engineering",
                "factory-security-review",
            }
        ),
        consumers={
            "factory-software-engineer": {
                "required": ("factory-tdd-implementation",),
                "task_optional": ("factory-cli-engineering",),
            }
        },
        superseded=frozenset(),
    )


def _skill_source(root: Path, skill_id: str) -> Path:
    source = root / skill_id
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: test Skill\n---\n# {skill_id}\n",
        encoding="utf-8",
    )
    return source


def _preparer(
    *,
    native: FakeNativeTaskRuntime,
    runner: FakeRunner,
    skill_sources: dict[str, Path],
    expected_digests: dict[str, str],
) -> HermesTaskSkillPreparer:
    return HermesTaskSkillPreparer(
        native=native,
        skill_registry=_registry(),
        admitted_skill_ids=frozenset(
            {"factory-tdd-implementation", "factory-cli-engineering"}
        ),
        skill_sources=skill_sources,
        expected_skill_digests=expected_digests,
        command_runner=runner,
    )


def test_required_only_task_needs_no_worktree_projection_or_trust(tmp_path: Path) -> None:
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-tdd-implementation",),
            workspace_kind="scratch",
        ),
        tmp_path / "worktree",
    )
    runner = FakeRunner([])
    preparer = _preparer(
        native=native,
        runner=runner,
        skill_sources={},
        expected_digests={},
    )

    preparer.prepare(board="jarvas-cli", task_id="t_1")

    assert not any(name == "resolve_workspace" for name, _ in native.calls)
    assert runner.calls == []


def test_optional_skill_is_projected_only_into_task_worktree_and_trusted(tmp_path: Path) -> None:
    source = _skill_source(tmp_path / "sources", "factory-cli-engineering")
    worktree = tmp_path / "repo" / ".worktrees" / "t_1"
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-cli-engineering", "factory-tdd-implementation"),
            workspace_kind="worktree",
        ),
        worktree,
    )
    runner = FakeRunner(
        [
            CommandResult(0, "trusted\n", ""),
            CommandResult(0, f'["{worktree.resolve()}"]\n', ""),
        ]
    )
    preparer = _preparer(
        native=native,
        runner=runner,
        skill_sources={"factory-cli-engineering": source},
        expected_digests={"factory-cli-engineering": digest_artifact(source)},
    )

    preparer.prepare(board="jarvas-cli", task_id="t_1")

    target = worktree / ".hermes" / "skills" / "factory-cli-engineering"
    assert (target / "SKILL.md").is_file()
    assert not (worktree / ".hermes" / "skills" / "factory-tdd-implementation").exists()
    assert runner.calls == [
        (
            "hermes",
            "-p",
            "factory-software-engineer",
            "skills",
            "trust",
            str(worktree.resolve()),
        ),
        (
            "hermes",
            "-p",
            "factory-software-engineer",
            "config",
            "get",
            "skills.trusted_project_dirs",
            "--json",
        ),
    ]


def test_optional_skill_requires_worktree_before_any_projection(tmp_path: Path) -> None:
    source = _skill_source(tmp_path / "sources", "factory-cli-engineering")
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-cli-engineering", "factory-tdd-implementation"),
            workspace_kind="scratch",
        ),
        tmp_path / "scratch",
    )
    runner = FakeRunner([])
    preparer = _preparer(
        native=native,
        runner=runner,
        skill_sources={"factory-cli-engineering": source},
        expected_digests={"factory-cli-engineering": digest_artifact(source)},
    )

    with pytest.raises(RuntimeError, match="worktree"):
        preparer.prepare(board="jarvas-cli", task_id="t_1")

    assert not (tmp_path / "scratch" / ".hermes").exists()
    assert runner.calls == []


def test_tampered_native_task_skill_set_fails_factory_authorization_before_workspace(
    tmp_path: Path,
) -> None:
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-security-review", "factory-tdd-implementation"),
            workspace_kind="worktree",
        ),
        tmp_path / "worktree",
    )
    preparer = _preparer(
        native=native,
        runner=FakeRunner([]),
        skill_sources={},
        expected_digests={},
    )

    with pytest.raises(SkillAdmissionError, match="not authorized"):
        preparer.prepare(board="jarvas-cli", task_id="t_1")

    assert not any(name == "resolve_workspace" for name, _ in native.calls)


def test_skill_source_digest_drift_fails_before_projection_or_trust(tmp_path: Path) -> None:
    source = _skill_source(tmp_path / "sources", "factory-cli-engineering")
    worktree = tmp_path / "worktree"
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-cli-engineering", "factory-tdd-implementation"),
            workspace_kind="worktree",
        ),
        worktree,
    )
    runner = FakeRunner([])
    preparer = _preparer(
        native=native,
        runner=runner,
        skill_sources={"factory-cli-engineering": source},
        expected_digests={"factory-cli-engineering": "sha256:stale"},
    )

    with pytest.raises(RuntimeError, match="digest"):
        preparer.prepare(board="jarvas-cli", task_id="t_1")

    assert not (worktree / ".hermes" / "skills" / "factory-cli-engineering").exists()
    assert runner.calls == []


def test_trust_verification_failure_untrusts_and_removes_new_projection(tmp_path: Path) -> None:
    source = _skill_source(tmp_path / "sources", "factory-cli-engineering")
    worktree = tmp_path / "worktree"
    native = FakeNativeTaskRuntime(
        FakeTask(
            assignee="factory-software-engineer",
            skills=("factory-cli-engineering", "factory-tdd-implementation"),
            workspace_kind="worktree",
        ),
        worktree,
    )
    runner = FakeRunner(
        [
            CommandResult(0, "trusted\n", ""),
            CommandResult(0, "[]\n", ""),
            CommandResult(0, "untrusted\n", ""),
        ]
    )
    preparer = _preparer(
        native=native,
        runner=runner,
        skill_sources={"factory-cli-engineering": source},
        expected_digests={"factory-cli-engineering": digest_artifact(source)},
    )

    with pytest.raises(RuntimeError, match="trust verification"):
        preparer.prepare(board="jarvas-cli", task_id="t_1")

    assert not (worktree / ".hermes" / "skills" / "factory-cli-engineering").exists()
    assert runner.calls[-1] == (
        "hermes",
        "-p",
        "factory-software-engineer",
        "skills",
        "untrust",
        str(worktree.resolve()),
    )
