from pathlib import Path

from hermes_factory.adapters.hermes_gateway import (
    GatewayHITLCallback,
    GatewayHITLProjectionError,
    HermesGatewayHITLAdapter,
)
from hermes_factory.traceability import SemanticRegistry
from hermes_factory.workflow import (
    HITLDecisionCommitError,
    HITLDecisionService,
    HITLRequest,
    HITLState,
)


def _request(state: HITLState = HITLState.PENDING) -> HITLRequest:
    return HITLRequest(
        request_id="HITL-42",
        request_version=3,
        context_revision="ctx-9",
        candidate_revision="abc123",
        allowed_responder="telegram:1001",
        state=state,
    )


def _projection(adapter: HermesGatewayHITLAdapter):
    return adapter.project_clarify(
        _request(),
        chat_id="1001",
        session_key="telegram:1001:factory",
        question="Choose",
        choices=("approve", "reject"),
    )


def test_gateway_callback_builds_exactly_bound_human_decision() -> None:
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)
    projection = _projection(adapter)

    decision = adapter.decision_from_callback(
        _request(),
        projection,
        GatewayHITLCallback(
            clarify_id=projection.clarify_id,
            responder_identity="telegram:1001",
            choice="approve",
        ),
    )

    assert decision.request_id == "HITL-42"
    assert decision.request_version == 3
    assert decision.context_revision == "ctx-9"
    assert decision.candidate_revision == "abc123"
    assert decision.responder_identity == "telegram:1001"
    assert decision.decision == "approve"


def test_gateway_callback_rejects_wrong_prompt_responder_or_choice() -> None:
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)
    projection = _projection(adapter)

    invalid_callbacks = (
        GatewayHITLCallback("hf:wrong", "telegram:1001", "approve"),
        GatewayHITLCallback(projection.clarify_id, "telegram:9999", "approve"),
        GatewayHITLCallback(projection.clarify_id, "telegram:1001", "invented"),
    )
    for callback in invalid_callbacks:
        try:
            adapter.decision_from_callback(_request(), projection, callback)
        except GatewayHITLProjectionError:
            pass
        else:
            raise AssertionError("unbound Gateway callback must fail closed")


def test_human_decision_is_committed_once_before_it_can_unlock(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    service = HITLDecisionService(registry)
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)
    projection = _projection(adapter)
    decision = adapter.decision_from_callback(
        _request(),
        projection,
        GatewayHITLCallback(
            projection.clarify_id,
            "telegram:1001",
            "approve",
        ),
    )

    committed = service.commit(_request(), decision)

    assert committed == decision
    records = registry.repository("HumanDecision").history("HITL-42")
    assert len(records) == 1
    assert records[0]["revision"] == "3"
    assert records[0]["payload"]["decision"] == "approve"
    events = registry.list_events(kind="HUMAN_DECISION_RECORDED")
    assert len(events) == 1
    assert events[0]["payload"]["request_id"] == "HITL-42"
    assert events[0]["payload"]["request_version"] == 3

    try:
        service.commit(_request(), decision)
    except HITLDecisionCommitError as error:
        assert "replay" in str(error)
    else:
        raise AssertionError("replayed HumanDecision must fail closed")


def test_non_pending_or_mismatched_decision_is_never_committed(tmp_path: Path) -> None:
    registry = SemanticRegistry(tmp_path / "factory.db")
    service = HITLDecisionService(registry)
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)
    projection = _projection(adapter)
    decision = adapter.decision_from_callback(
        _request(),
        projection,
        GatewayHITLCallback(
            projection.clarify_id,
            "telegram:1001",
            "approve",
        ),
    )

    for state in (
        HITLState.EXPIRED,
        HITLState.STALE,
        HITLState.CANCELLED,
        HITLState.DECIDED,
    ):
        try:
            service.commit(_request(state), decision)
        except HITLDecisionCommitError:
            pass
        else:
            raise AssertionError("non-pending HITL must not commit")

    assert registry.repository("HumanDecision").history("HITL-42") == []
    assert registry.list_events(kind="HUMAN_DECISION_RECORDED") == []
