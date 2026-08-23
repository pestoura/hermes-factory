from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from hermes_factory.domain import HandoffState
from hermes_factory.handoff.service import HandoffService
from hermes_factory.runtime.completion_handoff import (
    CompletionHandoffCoordinator,
    CompletionHandoffError,
)


@dataclass
class FakeTask:
    id: str
    assignee: str
    status: str
    idempotency_key: str | None


@dataclass
class FakeRun:
    outcome: str
    metadata: dict | None


class FakeNative:
    def __init__(self) -> None:
        self.tasks = {}
        self.runs = {}
        self.children = {}
        self.parents = {}

    @contextmanager
    def connect_closing(self, *, board: str):
        yield self

    def get_task(self, conn, task_id: str):
        return self.tasks.get(task_id)

    def latest_run(self, conn, task_id: str):
        return self.runs.get(task_id)

    def child_ids(self, conn, task_id: str):
        return list(self.children.get(task_id, ()))

    def parent_ids(self, conn, task_id: str):
        return list(self.parents.get(task_id, ()))


class FakeLedger:
    def __init__(self) -> None:
        self.entries = []

    def commit(self, record, state):
        self.entries.append((record, state))

    def set_state(self, handoff_id, state):
        self.entries.append((handoff_id, state))


class FakeAuthorizer:
    def __init__(self) -> None:
        self.calls = []

    def authorize_dispatch(self, **kwargs):
        self.calls.append(kwargs)


class FakeCandidateObserver:
    def __init__(self, identity: str | None = None) -> None:
        self.identity = identity
        self.calls = []

    def observe(self, *, board: str, task) -> str | None:
        self.calls.append((board, task.id))
        return self.identity


def _metadata(revision: str, *, candidate: str | None = None) -> dict:
    return {
        "factory_handoff": {
            "schema": "hermes.factory/handoff-completion/v1",
            "stage_outcome": "PASS",
            "artifact_refs": ["artifact:spec"],
            "evidence_refs": ["evidence:check"],
            "evidence_states": ["PASS"],
            "finding_state": "NONE",
            "context_revision": revision,
            "candidate_identity": candidate,
            "independent_review_state": None,
        }
    }


def _coordinator(native: FakeNative, *, observed_candidate: str | None = None):
    ledger = FakeLedger()
    authorizer = FakeAuthorizer()
    observer = FakeCandidateObserver(observed_candidate)
    service = HandoffService(ledger=ledger, kanban=authorizer)
    return (
        CompletionHandoffCoordinator(
            native=native,
            handoff_service=service,
            candidate_observer=observer,
        ),
        ledger,
        authorizer,
    )


def test_non_factory_completion_is_ignored() -> None:
    native = FakeNative()
    native.tasks["t_1"] = FakeTask("t_1", "someone", "done", None)
    coordinator, ledger, authorizer = _coordinator(native)

    assert coordinator.on_task_completed(task_id="t_1", board="misc") == ()
    assert ledger.entries == []
    assert authorizer.calls == []


def test_missing_structured_completion_fails_closed() -> None:
    revision = "a" * 64
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-requirements-engineer", "done",
        f"factory:jarvas-cli:WP-A:SPECIFY:{revision}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-software-architect", "blocked",
        f"factory:jarvas-cli:WP-A:DESIGN:{revision}",
    )
    native.runs["t_parent"] = FakeRun("completed", metadata={})
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent",)
    coordinator, ledger, authorizer = _coordinator(native)

    with pytest.raises(CompletionHandoffError, match="factory_handoff"):
        coordinator.on_task_completed(task_id="t_parent", board="jarvas-cli")
    assert ledger.entries == []
    assert authorizer.calls == []


def test_valid_completion_promotes_child_through_handoff_service() -> None:
    revision = "b" * 64
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-requirements-engineer", "done",
        f"factory:jarvas-cli:WP-A:SPECIFY:{revision}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-software-architect", "blocked",
        f"factory:jarvas-cli:WP-A:DESIGN:{revision}",
    )
    native.runs["t_parent"] = FakeRun("completed", metadata=_metadata(revision))
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent",)
    coordinator, ledger, authorizer = _coordinator(native)

    states = coordinator.on_task_completed(task_id="t_parent", board="jarvas-cli")

    assert states == (HandoffState.HANDED_OFF,)
    assert authorizer.calls == [
        {
            "board": "jarvas-cli",
            "task_id": "t_child",
            "actor": "factory-orchestrator",
            "source": "factory-continuous-handoff",
        }
    ]
    record, ready_state = ledger.entries[0]
    assert ready_state is HandoffState.HANDOFF_READY
    assert record.project_id == "jarvas-cli"
    assert record.work_package_id == "WP-A"
    assert record.stage == "SPECIFY"
    assert record.context_revision == revision
    assert record.candidate_identity_required is False


def test_other_open_parent_keeps_child_blocked() -> None:
    revision = "c" * 64
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-evidence-auditor", "done",
        f"factory:jarvas-cli:WP-A:ACCEPT:{revision}",
    )
    native.tasks["t_other"] = FakeTask(
        "t_other", "factory-evidence-auditor", "blocked",
        f"factory:jarvas-cli:WP-B:ACCEPT:{revision}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-requirements-engineer", "blocked",
        f"factory:jarvas-cli:WP-C:DISCOVER:{revision}",
    )
    native.runs["t_parent"] = FakeRun(
        "completed", metadata=_metadata(revision, candidate="d" * 40)
    )
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent", "t_other")
    coordinator, _ledger, authorizer = _coordinator(
        native, observed_candidate="d" * 40
    )

    states = coordinator.on_task_completed(task_id="t_parent", board="jarvas-cli")

    assert states == (HandoffState.HANDOFF_BLOCKED,)
    assert authorizer.calls == []


def test_candidate_bound_stage_uses_observed_git_identity_not_worker_assertion() -> None:
    revision = "e" * 64
    claimed = "1" * 40
    observed = "2" * 40
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-software-engineer", "done",
        f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-software-engineer", "blocked",
        f"factory:jarvas-cli:WP-A:UNIT:{revision}",
    )
    native.runs["t_parent"] = FakeRun(
        "completed", metadata=_metadata(revision, candidate=claimed)
    )
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent",)
    coordinator, ledger, authorizer = _coordinator(
        native, observed_candidate=observed
    )

    states = coordinator.on_task_completed(
        task_id="t_parent", board="jarvas-cli"
    )

    assert states == (HandoffState.STALE,)
    assert authorizer.calls == []
    record, state = ledger.entries[0]
    assert state is HandoffState.STALE
    assert record.candidate_identity == claimed


def test_versioned_stage_identity_uses_base_context_revision() -> None:
    revision = "f" * 64
    materialization = revision + ".stage-contract-v2"
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-requirements-engineer", "done",
        f"factory:jarvas-cli:WP-A:DISCOVER:{materialization}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-requirements-engineer", "blocked",
        f"factory:jarvas-cli:WP-A:SPECIFY:{materialization}",
    )
    native.runs["t_parent"] = FakeRun("completed", metadata=_metadata(revision))
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent",)
    coordinator, ledger, authorizer = _coordinator(native)

    states = coordinator.on_task_completed(task_id="t_parent", board="jarvas-cli")
    assert states == (HandoffState.HANDED_OFF,)
    assert authorizer.calls[0]["task_id"] == "t_child"
    record, _ = ledger.entries[0]
    assert record.context_revision == revision
    assert materialization in record.handoff_id


def test_invalid_stage_outcome_is_rejected_before_handoff() -> None:
    revision = "1" * 64
    native = FakeNative()
    native.tasks["t_parent"] = FakeTask(
        "t_parent", "factory-requirements-engineer", "done",
        f"factory:jarvas-cli:WP-A:DISCOVER:{revision}",
    )
    native.tasks["t_child"] = FakeTask(
        "t_child", "factory-requirements-engineer", "blocked",
        f"factory:jarvas-cli:WP-A:SPECIFY:{revision}",
    )
    metadata = _metadata(revision)
    metadata["factory_handoff"]["stage_outcome"] = "REQUIREMENTS_BASELINE"
    native.runs["t_parent"] = FakeRun("completed", metadata=metadata)
    native.children["t_parent"] = ("t_child",)
    native.parents["t_child"] = ("t_parent",)
    coordinator, ledger, authorizer = _coordinator(native)
    with pytest.raises(CompletionHandoffError, match="stage_outcome"):
        coordinator.on_task_completed(task_id="t_parent", board="jarvas-cli")
    assert ledger.entries == []
    assert authorizer.calls == []


def test_precompletion_rejects_pass_with_open_findings() -> None:
    from hermes_factory.runtime.completion_handoff import (
        validate_factory_completion_metadata,
    )

    revision = "2" * 64
    metadata = _metadata(revision)
    metadata["factory_handoff"]["finding_state"] = "OPEN"
    key = f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"

    with pytest.raises(CompletionHandoffError, match="finding_state"):
        validate_factory_completion_metadata(
            idempotency_key=key,
            metadata=metadata,
        )


def test_precompletion_accepts_ready_pass() -> None:
    from hermes_factory.runtime.completion_handoff import (
        validate_factory_completion_metadata,
    )

    revision = "3" * 64
    metadata = _metadata(revision)
    key = f"factory:jarvas-cli:WP-A:DISCOVER:{revision}.stage-contract-v3"

    payload = validate_factory_completion_metadata(
        idempotency_key=key,
        metadata=metadata,
    )

    assert payload["stage_outcome"] == "PASS"
    assert payload["finding_state"] == "NONE"
    assert payload["context_revision"] == revision


def test_precompletion_candidate_stage_requires_candidate_identity() -> None:
    from hermes_factory.runtime.completion_handoff import (
        validate_factory_completion_metadata,
    )

    revision = "6" * 64
    metadata = _metadata(revision)
    key = f"factory:jarvas-cli:WP-A:IMPLEMENT:{revision}.stage-contract-v4"

    with pytest.raises(CompletionHandoffError, match="candidate_identity"):
        validate_factory_completion_metadata(
            idempotency_key=key,
            metadata=metadata,
        )
