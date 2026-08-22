import json
from dataclasses import dataclass

import pytest

from hermes_factory.runtime.hermes_install_runtime import CommandResult
from hermes_factory.runtime.installed_completion import (
    GitCandidateIdentityObserver,
    InstalledRuntimeBindingError,
    active_factory_candidate_sha,
)


class FakeDistribution:
    def __init__(self, url: str | None) -> None:
        self.url = url

    def read_text(self, name: str) -> str | None:
        if name != "direct_url.json" or self.url is None:
            return None
        return json.dumps({"url": self.url})


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.calls = []

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(argv)
        return self.results.pop(0)


def test_active_candidate_sha_is_bound_to_installed_wheel_path() -> None:
    sha = "a" * 40
    dist = FakeDistribution(
        "file:///evidence/ci-artifacts/"
        f"factory-package-candidate-{sha}/hermes_factory-0.1.0-py3-none-any.whl"
    )
    assert active_factory_candidate_sha(distribution=dist) == sha


def test_active_candidate_sha_fails_closed_without_exact_candidate_path() -> None:
    with pytest.raises(InstalledRuntimeBindingError, match="direct_url"):
        active_factory_candidate_sha(distribution=FakeDistribution(None))
    with pytest.raises(InstalledRuntimeBindingError, match="candidate SHA"):
        active_factory_candidate_sha(
            distribution=FakeDistribution("file:///tmp/hermes_factory.whl")
        )


@dataclass
class FakeTask:
    id: str
    workspace_path: str | None


def test_git_candidate_observer_requires_clean_worktree_and_returns_head() -> None:
    sha = "b" * 40
    runner = FakeRunner([
        CommandResult(0, "", ""),
        CommandResult(0, sha + "\n", ""),
    ])
    observer = GitCandidateIdentityObserver(runner)
    task = FakeTask("t_1", "/repo/.worktrees/t_1")

    assert observer.observe(board="jarvas-cli", task=task) == sha
    assert runner.calls == [
        ("git", "-C", "/repo/.worktrees/t_1", "status", "--porcelain"),
        ("git", "-C", "/repo/.worktrees/t_1", "rev-parse", "HEAD"),
    ]


def test_git_candidate_observer_rejects_dirty_or_invalid_candidate() -> None:
    dirty = GitCandidateIdentityObserver(
        FakeRunner([CommandResult(0, " M src/x.py\n", "")])
    )
    with pytest.raises(InstalledRuntimeBindingError, match="dirty"):
        dirty.observe(
            board="jarvas-cli", task=FakeTask("t_1", "/repo/.worktrees/t_1")
        )
