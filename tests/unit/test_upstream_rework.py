from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from hermes_factory.runtime.upstream_rework import (
    UpstreamReworkCoordinator,
    UpstreamReworkError,
    UpstreamReworkRequest,
    parse_upstream_rework_request,
)

REV = "d" * 64
MATERIALIZATION = REV + ".stage-contract-v10"
PRODUCER_SHA = "a" * 40


@dataclass
class FakeTask:
    id: str
    assignee: str
    status: str
    idempotency_key: str
    skills: tuple[str, ...] = ()
    workspace_kind: str = "worktree"
    workspace_path: str | None = "/repo/.worktrees/shared"
    branch_name: str | None = "factory/jarvas/wp-a-v10"
    project_id: str | None = "p_1"
    current_run_id: int | None = 7


@dataclass
class FakeRun:
    outcome: str
    metadata: dict


class FakeNative:
    def __init__(self) -> None:
        self.tasks: dict[str, FakeTask] = {}
        self.runs: dict[str, FakeRun] = {}
        self.parents: dict[str, tuple[str, ...]] = {}
        self.links: list[tuple[str, str]] = []

    @contextmanager
    def connect_closing(self, *, board: str):
        yield self

    def get_task(self, conn, task_id: str):
        return self.tasks.get(task_id)

    def latest_run(self, conn, task_id: str):
        return self.runs.get(task_id)

    def parent_ids(self, conn, task_id: str):
        return list(self.parents.get(task_id, ()))

    def link_tasks(self, conn, parent_id: str, child_id: str) -> None:
        link = (parent_id, child_id)
        if link not in self.links:
            self.links.append(link)
        parents = list(self.parents.get(child_id, ()))
        if parent_id not in parents:
            parents.append(parent_id)
            self.parents[child_id] = tuple(parents)


class FakeAdapter:
    def __init__(self, native: FakeNative) -> None:
        self.native = native
        self.projected = []
        self.authorized = []

    def project_task(self, spec):
        self.projected.append(spec)
        task_id = "t_rework"
        if task_id not in self.native.tasks:
            self.native.tasks[task_id] = FakeTask(
                id=task_id,
                assignee=spec.assignee,
                status="blocked",
                idempotency_key=spec.idempotency_key,
                skills=spec.approved_skills,
                workspace_kind=spec.workspace_kind,
                workspace_path=spec.workspace_path,
                branch_name=spec.branch_name,
                project_id=spec.project_id,
                current_run_id=None,
            )
        return task_id

    def authorize_dispatch(self, **kwargs):
        self.authorized.append(kwargs)
        self.native.tasks[kwargs["task_id"]].status = "ready"


class FakeCandidateObserver:
    def __init__(self, sha: str) -> None:
        self.sha = sha
        self.calls = []

    def observe(self, *, board: str, task: object):
        self.calls.append((board, task.id))
        return self.sha


def _handoff(candidate: str) -> dict:
    return {
        "factory_handoff": {
            "candidate_identity": candidate,
            "context_revision": REV,
        }
    }


def _setup() -> tuple[FakeNative, FakeAdapter, UpstreamReworkCoordinator]:
    native = FakeNative()
    producer = FakeTask(
        "t_red", "factory-tdd-red", "done",
        f"factory:jarvas-cli:WP-A:TDD_RED:{MATERIALIZATION}",
        skills=("factory-writing-causal-red-tests",), current_run_id=None,
    )
    consumer = FakeTask(
        "t_impl", "factory-software-engineer", "running",
        f"factory:jarvas-cli:WP-A:IMPLEMENT:{MATERIALIZATION}",
    )
    native.tasks.update({producer.id: producer, consumer.id: consumer})
    native.parents[consumer.id] = (producer.id,)
    native.runs[producer.id] = FakeRun("completed", _handoff(PRODUCER_SHA))
    adapter = FakeAdapter(native)
    coordinator = UpstreamReworkCoordinator(
        native=native,
        adapter=adapter,
        candidate_observer=FakeCandidateObserver(PRODUCER_SHA),
    )
    return native, adapter, coordinator




def _setup_review_with_ancestor_repair() -> tuple[FakeNative, FakeAdapter, UpstreamReworkCoordinator]:
    native = FakeNative()
    implement = FakeTask(
        "t_implement", "factory-software-engineer", "done",
        f"factory:jarvas-cli:WP-A:IMPLEMENT:{MATERIALIZATION}",
        skills=("factory-implementing-minimal-green",), current_run_id=None,
    )
    unit = FakeTask(
        "t_unit", "factory-software-engineer", "done",
        f"factory:jarvas-cli:WP-A:UNIT:{MATERIALIZATION}",
        skills=("factory-producing-evidence-handoffs",), current_run_id=None,
    )
    review = FakeTask(
        "t_review", "factory-code-reviewer", "running",
        f"factory:jarvas-cli:WP-A:CODE_REVIEW:{MATERIALIZATION}",
    )
    native.tasks.update({implement.id: implement, unit.id: unit, review.id: review})
    native.parents[unit.id] = (implement.id,)
    native.parents[review.id] = (unit.id,)
    native.runs[implement.id] = FakeRun("completed", _handoff("b" * 40))
    native.runs[unit.id] = FakeRun("completed", _handoff(PRODUCER_SHA))
    adapter = FakeAdapter(native)
    coordinator = UpstreamReworkCoordinator(
        native=native,
        adapter=adapter,
        candidate_observer=FakeCandidateObserver(PRODUCER_SHA),
    )
    return native, adapter, coordinator

def test_parse_structured_upstream_rework_request() -> None:
    reason = (
        '[factory:upstream-rework/v1] '
        '{"producer_stage":"TDD_RED","finding":"RED tests contradict the spec",'
        '"evidence_refs":["tests/test_cli_core.py"]}'
    )
    request = parse_upstream_rework_request(reason)
    assert request == UpstreamReworkRequest(
        producer_stage="TDD_RED",
        finding="RED tests contradict the spec",
        evidence_refs=("tests/test_cli_core.py",),
    )




def test_parse_upstream_rework_request_accepts_distinct_repair_stage() -> None:
    reason = (
        '[factory:upstream-rework/v1] '
        '{"producer_stage":"UNIT","repair_stage":"IMPLEMENT",'
        '"finding":"production defect behind unit checkpoint",'
        '"evidence_refs":["jarvas_cli/cli.py"]}'
    )
    request = parse_upstream_rework_request(reason)
    assert request == UpstreamReworkRequest(
        producer_stage="UNIT",
        finding="production defect behind unit checkpoint",
        evidence_refs=("jarvas_cli/cli.py",),
        repair_stage="IMPLEMENT",
    )


def test_parse_upstream_rework_request_rejects_unknown_repair_stage() -> None:
    reason = (
        '[factory:upstream-rework/v1] '
        '{"producer_stage":"UNIT","repair_stage":"NOT_A_STAGE",'
        '"finding":"bad routing","evidence_refs":["jarvas_cli/cli.py"]}'
    )
    with pytest.raises(UpstreamReworkError, match="unknown repair stage"):
        parse_upstream_rework_request(reason)


def test_schedule_rework_uses_ancestor_repair_stage_authority_on_direct_parent_candidate() -> None:
    native, adapter, coordinator = _setup_review_with_ancestor_repair()
    request = UpstreamReworkRequest(
        producer_stage="UNIT",
        finding="production defect behind unit checkpoint",
        evidence_refs=("jarvas_cli/cli.py",),
        repair_stage="IMPLEMENT",
    )

    task_id = coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_review", request=request
    )

    assert task_id == "t_rework"
    assert native.links == [("t_rework", "t_review")]
    spec = adapter.projected[0]
    assert spec.stage == "IMPLEMENT"
    assert spec.title.startswith("WP-A/IMPLEMENT rework via UNIT checkpoint:")
    assert spec.assignee == "factory-software-engineer"
    assert spec.approved_skills == ("factory-implementing-minimal-green",)
    assert spec.parent_task_ids == ("t_unit",)
    assert "~rework-unit-r7-" in spec.work_package_id
    assert "Producer stage: UNIT" in spec.body
    assert "Repair stage: IMPLEMENT" in spec.body
    assert "repository_mutation_policy=implementation_no_tests" in spec.body


def test_schedule_rework_rejects_repair_stage_that_is_not_an_ancestor() -> None:
    _, adapter, coordinator = _setup_review_with_ancestor_repair()
    request = UpstreamReworkRequest(
        producer_stage="UNIT",
        finding="invalid repair authority",
        evidence_refs=("jarvas_cli/cli.py",),
        repair_stage="DESIGN",
    )

    with pytest.raises(UpstreamReworkError, match="repair_stage.*ancestor"):
        coordinator.schedule(
            board="jarvas-cli", consumer_task_id="t_review", request=request
        )
    assert adapter.projected == []


def test_activate_pending_rework_with_distinct_repair_stage_authorizes_rework() -> None:
    native, adapter, coordinator = _setup_review_with_ancestor_repair()
    request = UpstreamReworkRequest(
        producer_stage="UNIT",
        finding="production defect behind unit checkpoint",
        evidence_refs=("jarvas_cli/cli.py",),
        repair_stage="IMPLEMENT",
    )
    coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_review", request=request
    )
    native.tasks["t_review"].status = "todo"
    native.tasks["t_review"].current_run_id = None

    task_id = coordinator.activate_pending(
        board="jarvas-cli", consumer_task_id="t_review", request=request
    )

    assert task_id == "t_rework"
    assert adapter.authorized == [{
        "board": "jarvas-cli",
        "task_id": "t_rework",
        "actor": "factory-orchestrator",
        "source": "factory-upstream-rework",
    }]

def test_non_rework_reason_is_not_claimed_by_factory() -> None:
    assert parse_upstream_rework_request("provider temporarily unavailable") is None


def test_schedule_rework_rejects_non_parent_stage() -> None:
    _, _, coordinator = _setup()
    request = UpstreamReworkRequest("DESIGN", "bad design", ("docs/design.md",))
    with pytest.raises(UpstreamReworkError, match="direct parent"):
        coordinator.schedule(
            board="jarvas-cli", consumer_task_id="t_impl", request=request
        )


def test_schedule_rework_requires_clean_consumer_at_producer_candidate() -> None:
    native, adapter, _ = _setup()
    coordinator = UpstreamReworkCoordinator(
        native=native,
        adapter=adapter,
        candidate_observer=FakeCandidateObserver("b" * 40),
    )
    request = UpstreamReworkRequest(
        "TDD_RED", "contradictory tests", ("tests/test_cli_core.py",)
    )
    with pytest.raises(UpstreamReworkError, match="producer candidate"):
        coordinator.schedule(
            board="jarvas-cli", consumer_task_id="t_impl", request=request
        )
    assert adapter.projected == []


def test_schedule_rework_projects_append_only_parent_and_authorizes_it() -> None:
    native, adapter, coordinator = _setup()
    request = UpstreamReworkRequest(
        "TDD_RED", "contradictory tests", ("tests/test_cli_core.py",)
    )
    task_id = coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_impl", request=request
    )

    assert task_id == "t_rework"
    assert native.links == [("t_rework", "t_impl")]
    assert len(adapter.projected) == 1
    spec = adapter.projected[0]
    assert spec.stage == "TDD_RED"
    assert spec.assignee == "factory-tdd-red"
    assert spec.approved_skills == ("factory-writing-causal-red-tests",)
    assert spec.workspace_path == "/repo/.worktrees/shared"
    assert spec.branch_name == "factory/jarvas/wp-a-v10"
    assert spec.parent_task_ids == ("t_red",)
    assert spec.revision == MATERIALIZATION
    assert "~rework-tdd_red-r7-" in spec.work_package_id
    assert "contradictory tests" in spec.body
    assert "tests/test_cli_core.py" in spec.body
    assert "repository_mutation_policy=tests_and_docs_only" in spec.body
    assert adapter.authorized == []


def test_schedule_rework_is_idempotent_within_consumer_run() -> None:
    native, adapter, coordinator = _setup()
    request = UpstreamReworkRequest(
        "TDD_RED", "contradictory tests", ("tests/test_cli_core.py",)
    )
    first = coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_impl", request=request
    )
    second = coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_impl", request=request
    )
    assert first == second == "t_rework"
    assert native.links == [("t_rework", "t_impl")]
    assert adapter.authorized == []


def test_rework_task_key_requires_factory_managed_suffix() -> None:
    from hermes_factory.runtime.upstream_rework import is_upstream_rework_task_key

    assert not is_upstream_rework_task_key(
        f"factory:jarvas-cli:WP-A~rework-notes:TDD_RED:{MATERIALIZATION}"
    )
    assert is_upstream_rework_task_key(
        "factory:jarvas-cli:WP-A~rework-tdd_red-r7-deadbeef1234:"
        f"TDD_RED:{MATERIALIZATION}"
    )


def test_schedule_rework_rejects_pre_v10_consumer() -> None:
    native, adapter, coordinator = _setup()
    native.tasks["t_impl"].idempotency_key = (
        f"factory:jarvas-cli:WP-A:IMPLEMENT:{REV}.stage-contract-v9"
    )
    native.tasks["t_red"].idempotency_key = (
        f"factory:jarvas-cli:WP-A:TDD_RED:{REV}.stage-contract-v9"
    )
    request = UpstreamReworkRequest(
        "TDD_RED", "contradictory tests", ("tests/test_cli_core.py",)
    )

    with pytest.raises(UpstreamReworkError, match="stage-contract-v10"):
        coordinator.schedule(
            board="jarvas-cli", consumer_task_id="t_impl", request=request
        )
    assert adapter.projected == []


def test_activate_pending_rework_waits_until_consumer_is_dependency_todo() -> None:
    native, adapter, coordinator = _setup()
    request = UpstreamReworkRequest(
        "TDD_RED", "contradictory tests", ("tests/test_cli_core.py",)
    )
    coordinator.schedule(
        board="jarvas-cli", consumer_task_id="t_impl", request=request
    )

    with pytest.raises(UpstreamReworkError, match="dependency wait"):
        coordinator.activate_pending(
            board="jarvas-cli", consumer_task_id="t_impl", request=request
        )
    assert adapter.authorized == []

    native.tasks["t_impl"].status = "todo"
    native.tasks["t_impl"].current_run_id = None
    task_id = coordinator.activate_pending(
        board="jarvas-cli", consumer_task_id="t_impl", request=request
    )

    assert task_id == "t_rework"
    assert adapter.authorized == [{
        "board": "jarvas-cli",
        "task_id": "t_rework",
        "actor": "factory-orchestrator",
        "source": "factory-upstream-rework",
    }]
