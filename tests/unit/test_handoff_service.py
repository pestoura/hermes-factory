from dataclasses import replace

from hermes_factory.handoff.service import (
    HandoffRecord,
    HandoffService,
    HandoffState,
)


class FakeLedger:
    def __init__(self, events: list[tuple[str, object]] | None = None) -> None:
        self.records: dict[str, tuple[HandoffRecord, HandoffState]] = {}
        self.events = events if events is not None else []

    def commit(self, record: HandoffRecord, state: HandoffState) -> None:
        existing = self.records.get(record.handoff_id)
        if existing is not None and existing != (record, state):
            raise RuntimeError("immutable handoff conflict")
        self.records[record.handoff_id] = (record, state)
        self.events.append(("commit", state))

    def set_state(self, handoff_id: str, state: HandoffState) -> None:
        record, _ = self.records[handoff_id]
        self.records[handoff_id] = (record, state)
        self.events.append(("set_state", state))


class FakeKanban:
    def __init__(self, events: list[tuple[str, object]] | None = None) -> None:
        self.approvals: list[tuple[str, str, str, str]] = []
        self.events = events if events is not None else []

    def authorize_dispatch(self, *, board: str, task_id: str, actor: str, source: str) -> None:
        self.approvals.append((board, task_id, actor, source))
        self.events.append(("authorize", task_id))


def _record() -> HandoffRecord:
    return HandoffRecord(
        handoff_id="H-1",
        project_id="jarvas-cli",
        work_package_id="WP-1",
        stage="IMPLEMENT",
        producer_profile="factory-software-engineer",
        stage_outcome="PASS",
        artifact_refs=("artifact:diff",),
        evidence_refs=("evidence:unit",),
        evidence_states=("PASS",),
        finding_state="NONE",
        next_stage_prerequisites=(True,),
        context_revision="ctx-7",
        candidate_identity="abc123",
        candidate_identity_required=True,
        independent_review_required=False,
        independent_review_state=None,
    )


def test_ready_handoff_is_committed_before_native_authorization() -> None:
    events: list[tuple[str, object]] = []
    ledger = FakeLedger(events)
    kanban = FakeKanban(events)
    service = HandoffService(ledger=ledger, kanban=kanban)

    state = service.promote(
        _record(),
        current_context_revision="ctx-7",
        current_candidate_identity="abc123",
        next_board="jarvas-cli",
        next_task_id="t_review",
        actor="factory-orchestrator",
    )

    assert state is HandoffState.HANDED_OFF
    assert ledger.records["H-1"][1] is HandoffState.HANDED_OFF
    assert kanban.approvals == [
        ("jarvas-cli", "t_review", "factory-orchestrator", "factory-continuous-handoff")
    ]
    assert events == [
        ("commit", HandoffState.HANDOFF_READY),
        ("authorize", "t_review"),
        ("set_state", HandoffState.HANDED_OFF),
    ]


def test_non_pass_or_stale_evidence_cannot_authorize_next_task() -> None:
    ledger = FakeLedger()
    kanban = FakeKanban()
    service = HandoffService(ledger=ledger, kanban=kanban)

    blocked = service.promote(
        replace(_record(), evidence_states=("STALE",)),
        current_context_revision="ctx-7",
        current_candidate_identity="abc123",
        next_board="jarvas-cli",
        next_task_id="t_review",
        actor="factory-orchestrator",
    )

    assert blocked is HandoffState.HANDOFF_BLOCKED
    assert kanban.approvals == []


def test_context_or_candidate_change_marks_handoff_stale_without_authorization() -> None:
    ledger = FakeLedger()
    kanban = FakeKanban()
    service = HandoffService(ledger=ledger, kanban=kanban)

    stale = service.promote(
        _record(),
        current_context_revision="ctx-8",
        current_candidate_identity="def456",
        next_board="jarvas-cli",
        next_task_id="t_review",
        actor="factory-orchestrator",
    )

    assert stale is HandoffState.STALE
    assert ledger.records["H-1"][1] is HandoffState.STALE
    assert kanban.approvals == []


def test_candidate_identity_and_independent_review_are_fail_closed_when_required() -> None:
    ledger = FakeLedger()
    kanban = FakeKanban()
    service = HandoffService(ledger=ledger, kanban=kanban)

    no_candidate = service.promote(
        replace(_record(), candidate_identity=None),
        current_context_revision="ctx-7",
        current_candidate_identity=None,
        next_board="jarvas-cli",
        next_task_id="t_review",
        actor="factory-orchestrator",
    )
    review_not_run = service.promote(
        replace(
            _record(),
            handoff_id="H-2",
            independent_review_required=True,
            independent_review_state="NOT_RUN",
        ),
        current_context_revision="ctx-7",
        current_candidate_identity="abc123",
        next_board="jarvas-cli",
        next_task_id="t_security",
        actor="factory-orchestrator",
    )

    assert no_candidate is HandoffState.HANDOFF_BLOCKED
    assert review_not_run is HandoffState.HANDOFF_BLOCKED
    assert kanban.approvals == []
