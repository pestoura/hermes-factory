import json
from contextlib import contextmanager
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


class FakeCandidateObserver:
    def __init__(self, observed: str | None = None, error: Exception | None = None) -> None:
        self.observed = observed
        self.error = error
        self.calls = []

    def observe(self, *, board: str, task: object) -> str | None:
        self.calls.append((board, task))
        if self.error is not None:
            raise self.error
        return self.observed


def test_precompletion_repository_validation_observes_clean_head() -> None:
    sha = "d" * 40
    task = FakeTask("t_1", "/repo/.worktrees/t_1")
    observer = FakeCandidateObserver(sha)

    observed = installed_completion.validate_factory_repository_precompletion(
        board="jarvas-cli", task=task, candidate_identity=None, observer=observer,
    )

    assert observed == sha
    assert observer.calls == [("jarvas-cli", task)]


def test_precompletion_repository_validation_rejects_candidate_mismatch() -> None:
    task = FakeTask("t_1", "/repo/.worktrees/t_1")
    observer = FakeCandidateObserver("e" * 40)

    with pytest.raises(InstalledRuntimeBindingError, match="does not match"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli", task=task, candidate_identity="f" * 40, observer=observer,
        )


def test_precompletion_repository_validation_propagates_dirty_worktree() -> None:
    task = FakeTask("t_1", "/repo/.worktrees/t_1")
    observer = FakeCandidateObserver(
        error=InstalledRuntimeBindingError("candidate worktree is dirty")
    )

    with pytest.raises(InstalledRuntimeBindingError, match="dirty"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli", task=task, candidate_identity=None, observer=observer,
        )


class FakeMutationObserver:
    def __init__(self, paths: tuple[str, ...]) -> None:
        self.paths = paths
        self.calls = []

    def observe(self, *, task: object, base_candidate_identity: str | None) -> tuple[str, ...]:
        self.calls.append((task, base_candidate_identity))
        return self.paths


def test_design_precompletion_rejects_production_source_delta() -> None:
    task = FakeTask("t_design", "/repo/.worktrees/t_design")
    candidate = "1" * 40
    mutation = FakeMutationObserver(("docs/adr/ADR-0001.md", "jarvas_cli/contracts.py"))

    with pytest.raises(InstalledRuntimeBindingError, match="DESIGN.*production"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli",
            task=task,
            candidate_identity=candidate,
            observer=FakeCandidateObserver(candidate),
            stage="DESIGN",
            base_candidate_identity="0" * 40,
            mutation_observer=mutation,
        )


def test_tdd_red_allows_tests_but_rejects_production_source() -> None:
    installed_completion.validate_factory_stage_mutation_paths(
        stage="TDD_RED",
        changed_paths=("tests/test_contracts.py", "tests/fixtures/result.json"),
    )
    with pytest.raises(InstalledRuntimeBindingError, match="TDD_RED.*production"):
        installed_completion.validate_factory_stage_mutation_paths(
            stage="TDD_RED",
            changed_paths=("tests/test_contracts.py", "jarvas_cli/contracts.py"),
        )


def test_implement_allows_production_but_rejects_red_test_rewrites() -> None:
    installed_completion.validate_factory_stage_mutation_paths(
        stage="IMPLEMENT",
        changed_paths=("jarvas_cli/contracts.py", "pyproject.toml"),
    )
    with pytest.raises(InstalledRuntimeBindingError, match="IMPLEMENT.*test"):
        installed_completion.validate_factory_stage_mutation_paths(
            stage="IMPLEMENT",
            changed_paths=("jarvas_cli/contracts.py", "tests/test_contracts.py"),
        )


def test_git_stage_mutation_observer_diffs_from_parent_candidate() -> None:
    base = "2" * 40
    runner = FakeRunner([
        CommandResult(0, "docs/adr/ADR-0001.md\njarvas_cli/contracts.py\n", ""),
    ])
    observer = installed_completion.GitStageMutationObserver(runner)
    task = FakeTask("t_design", "/repo/.worktrees/t_design")

    assert observer.observe(task=task, base_candidate_identity=base) == (
        "docs/adr/ADR-0001.md",
        "jarvas_cli/contracts.py",
    )
    assert runner.calls == [
        (
            "git", "-C", "/repo/.worktrees/t_design", "diff", "--name-only",
            "--diff-filter=ACMRD", f"{base}..HEAD", "--",
        )
    ]


@dataclass
class FakeFactoryTask(FakeTask):
    idempotency_key: str | None = None


def test_precompletion_derives_stage_and_parent_candidate_from_factory_task(monkeypatch) -> None:
    revision = "3" * 64
    candidate = "4" * 40
    parent = "5" * 40
    task = FakeFactoryTask(
        "t_design",
        "/repo/.worktrees/t_design",
        f"factory:jarvas-cli:WP-A:DESIGN:{revision}.stage-contract-v9",
    )
    mutation = FakeMutationObserver(("jarvas_cli/contracts.py",))
    seen = []
    monkeypatch.setattr(
        installed_completion,
        "_parent_candidate_identity",
        lambda *, board, task: seen.append((board, task.id)) or parent,
        raising=False,
    )

    with pytest.raises(InstalledRuntimeBindingError, match="DESIGN.*production"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli",
            task=task,
            candidate_identity=candidate,
            observer=FakeCandidateObserver(candidate),
            mutation_observer=mutation,
        )

    assert seen == [("jarvas-cli", "t_design")]
    assert mutation.calls == [(task, parent)]


def test_design_allows_engineering_documentation_delta() -> None:
    installed_completion.validate_factory_stage_mutation_paths(
        stage="DESIGN",
        changed_paths=("docs/adr/ADR-0001.md", "architecture.drawio"),
    )


def test_root_stage_mutation_observer_uses_latest_checkpoint_commit() -> None:
    runner = FakeRunner([CommandResult(0, "docs/requirements.md\n", "")])
    observer = installed_completion.GitStageMutationObserver(runner)
    task = FakeTask("t_discover", "/repo/.worktrees/t_discover")

    assert observer.observe(task=task, base_candidate_identity=None) == (
        "docs/requirements.md",
    )
    assert runner.calls == [
        (
            "git", "-C", "/repo/.worktrees/t_discover", "diff-tree",
            "--no-commit-id", "--name-only", "-r", "HEAD", "--",
        )
    ]


def test_parent_candidate_identity_reads_structured_parent_handoff(monkeypatch) -> None:
    candidate = "6" * 40

    class FakeKB:
        @staticmethod
        @contextmanager
        def connect_closing(*, board: str):
            assert board == "jarvas-cli"
            yield object()

        @staticmethod
        def parent_ids(conn, task_id: str):
            assert task_id == "t_design"
            return ["t_specify"]

        @staticmethod
        def latest_run(conn, task_id: str):
            assert task_id == "t_specify"
            return type("Run", (), {
                "metadata": {
                    "factory_handoff": {"candidate_identity": candidate}
                }
            })()

    monkeypatch.setattr(installed_completion, "import_module", lambda _: FakeKB)
    task = FakeFactoryTask("t_design", "/repo/.worktrees/t_design", None)

    assert installed_completion._parent_candidate_identity(
        board="jarvas-cli", task=task
    ) == candidate


def test_parent_candidate_identity_prefers_single_rework_parent(monkeypatch) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    original = "1" * 40
    corrected = "2" * 40
    revision = "3" * 64

    class FakeKB:
        @staticmethod
        @contextmanager
        def connect_closing(*, board: str):
            yield object()

        @staticmethod
        def parent_ids(conn, task_id: str):
            return ["t_original", "t_rework"]

        @staticmethod
        def get_task(conn, task_id: str):
            keys = {
                "t_original": f"factory:jarvas-cli:WP-A:TDD_RED:{revision}.stage-contract-v10",
                "t_rework": (
                    "factory:jarvas-cli:WP-A~rework-tdd_red-r7-deadbeef1234:"
                    f"TDD_RED:{revision}.stage-contract-v10"
                ),
            }
            return SimpleNamespace(idempotency_key=keys[task_id])

        @staticmethod
        def latest_run(conn, task_id: str):
            candidate = original if task_id == "t_original" else corrected
            return SimpleNamespace(
                metadata={"factory_handoff": {"candidate_identity": candidate}}
            )

    monkeypatch.setattr(installed_completion, "import_module", lambda _: FakeKB)
    task = SimpleNamespace(id="t_consumer")

    assert installed_completion._parent_candidate_identity(
        board="jarvas-cli", task=task
    ) == corrected


def test_v11_discover_rejects_cross_stage_documentation(monkeypatch) -> None:
    revision = "a" * 64
    candidate = "1" * 40
    task = FakeFactoryTask(
        "t_discover",
        "/repo/.worktrees/t_discover",
        f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v11",
    )
    mutation = FakeMutationObserver((
        "docs/factory/WP-A/DISCOVER/requirements.md",
        "docs/factory/WP-A/SPECIFY/specification.md",
    ))
    monkeypatch.setattr(
        installed_completion,
        "_parent_candidate_identity",
        lambda **_: "0" * 40,
    )

    with pytest.raises(InstalledRuntimeBindingError, match="DISCOVER.*artifact namespace"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli", task=task, candidate_identity=candidate,
            observer=FakeCandidateObserver(candidate), mutation_observer=mutation,
        )

def test_v11_specify_requires_own_stage_delta(monkeypatch) -> None:
    revision = "b" * 64
    candidate = "2" * 40
    task = FakeFactoryTask(
        "t_specify",
        "/repo/.worktrees/t_specify",
        f"factory:jarvas-cli:WP-A:SPECIFY:{revision}.stage-contract-v11",
    )
    mutation = FakeMutationObserver(())
    monkeypatch.setattr(
        installed_completion,
        "_parent_candidate_identity",
        lambda **_: "3" * 40,
    )

    with pytest.raises(InstalledRuntimeBindingError, match="SPECIFY.*stage-owned"):
        installed_completion.validate_factory_repository_precompletion(
            board="jarvas-cli", task=task, candidate_identity=candidate,
            observer=FakeCandidateObserver(candidate), mutation_observer=mutation,
        )


def test_v11_owned_engineering_stage_delta_passes(monkeypatch) -> None:
    revision = "d" * 64
    candidate = "4" * 40
    task = FakeFactoryTask(
        "t_discover",
        "/repo/.worktrees/t_discover",
        f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v11",
    )
    mutation = FakeMutationObserver(("docs/factory/WP-A/DISCOVER/requirements.md",))
    monkeypatch.setattr(
        installed_completion,
        "_parent_candidate_identity",
        lambda **_: "5" * 40,
    )

    assert installed_completion.validate_factory_repository_precompletion(
        board="jarvas-cli", task=task, candidate_identity=candidate,
        observer=FakeCandidateObserver(candidate), mutation_observer=mutation,
    ) == candidate

def test_v10_docs_behavior_remains_backward_compatible(monkeypatch) -> None:
    revision = "e" * 64
    candidate = "6" * 40
    task = FakeFactoryTask(
        "t_discover_v10",
        "/repo/.worktrees/t_discover_v10",
        f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v10",
    )
    mutation = FakeMutationObserver(("docs/specs/legacy-requirements.md",))
    monkeypatch.setattr(
        installed_completion,
        "_parent_candidate_identity",
        lambda **_: "7" * 40,
    )

    assert installed_completion.validate_factory_repository_precompletion(
        board="jarvas-cli", task=task, candidate_identity=candidate,
        observer=FakeCandidateObserver(candidate), mutation_observer=mutation,
    ) == candidate
