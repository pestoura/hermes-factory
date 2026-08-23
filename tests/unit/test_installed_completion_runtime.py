import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from hermes_factory.runtime import installed_completion
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


def test_profile_scoped_hermes_home_resolves_shared_factory_root(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "hermes"
    profile = root / "profiles" / "factory-requirements-engineer"
    profile.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.delenv("HERMES_FACTORY_HOME", raising=False)

    assert installed_completion.resolve_shared_hermes_home() == root


def test_factory_home_override_wins_over_profile_home(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "hermes"
    profile = root / "profiles" / "factory-requirements-engineer"
    shared = tmp_path / "shared-hermes"
    profile.mkdir(parents=True)
    shared.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.setenv("HERMES_FACTORY_HOME", str(shared))

    assert installed_completion.resolve_shared_hermes_home() == shared


def test_completion_builder_loads_catalog_from_shared_root(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "hermes"
    profile = root / "profiles" / "factory-requirements-engineer"
    profile.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.delenv("HERMES_FACTORY_HOME", raising=False)
    sha = "c" * 40
    monkeypatch.setattr(installed_completion, "active_factory_candidate_sha", lambda: sha)
    monkeypatch.setattr(installed_completion, "import_module", lambda _: object())

    import hermes_factory.runtime.skill_catalog_candidate as skill_catalog
    seen = {}

    def stop_after_path_capture(*, candidate_root, expected_candidate_sha):
        seen["candidate_root"] = candidate_root
        seen["expected_candidate_sha"] = expected_candidate_sha
        raise RuntimeError("path captured")

    monkeypatch.setattr(skill_catalog, "load_skill_catalog_candidate", stop_after_path_capture)
    with pytest.raises(RuntimeError, match="path captured"):
        installed_completion.build_installed_completion_coordinator()

    assert seen == {
        "candidate_root": root / "factory" / "skill-catalog" / sha,
        "expected_candidate_sha": sha,
    }
