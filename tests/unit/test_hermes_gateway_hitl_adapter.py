from hermes_factory.adapters.hermes_gateway import (
    GatewayHITLProjectionError,
    HermesGatewayHITLAdapter,
)

from hermes_factory.workflow import HITLRequest, HITLState


def _request() -> HITLRequest:
    return HITLRequest(
        request_id="HITL-42",
        request_version=3,
        context_revision="ctx-9",
        candidate_revision="abc123",
        allowed_responder="telegram:1001",
        state=HITLState.PENDING,
    )


def test_hitl_projects_to_native_hermes_clarify_contract() -> None:
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)

    projection = adapter.project_clarify(
        _request(),
        chat_id="1001",
        session_key="telegram:1001:factory",
        question="Approve this bounded architecture decision?",
        choices=("approve", "reject"),
    )

    assert projection.surface == "send_clarify"
    assert projection.platform == "telegram"
    assert projection.allowed_responder == "telegram:1001"
    assert projection.gateway_kwargs() == {
        "chat_id": "1001",
        "question": "Approve this bounded architecture decision?",
        "choices": ["approve", "reject"],
        "clarify_id": projection.clarify_id,
        "session_key": "telegram:1001:factory",
    }
    assert projection.clarify_id.startswith("hf:")
    assert len(projection.clarify_id.encode("utf-8")) <= 64


def test_hitl_projection_is_bound_to_request_identity_without_leaking_revisions() -> None:
    adapter = HermesGatewayHITLAdapter(redact_text=lambda value: value)

    first = adapter.project_clarify(
        _request(),
        chat_id="1001",
        session_key="telegram:1001:factory",
        question="Select one option",
        choices=("A", "B"),
    )
    second = adapter.project_clarify(
        _request(),
        chat_id="1001",
        session_key="telegram:1001:factory",
        question="Select one option",
        choices=("A", "B"),
    )

    assert first.clarify_id == second.clarify_id
    rendered = str(first.gateway_kwargs())
    assert "ctx-9" not in rendered
    assert "abc123" not in rendered


def test_hitl_projection_fails_closed_if_prompt_or_choice_contains_sensitive_material() -> None:
    def redact(value: str) -> str:
        return value.replace("SECRET-42", "[REDACTED]")

    adapter = HermesGatewayHITLAdapter(redact_text=redact)

    try:
        adapter.project_clarify(
            _request(),
            chat_id="1001",
            session_key="telegram:1001:factory",
            question="Token is SECRET-42",
            choices=("approve", "reject"),
        )
    except GatewayHITLProjectionError as error:
        assert "sensitive" in str(error)
    else:
        raise AssertionError("sensitive HITL prompt must fail closed")

    try:
        adapter.project_clarify(
            _request(),
            chat_id="1001",
            session_key="telegram:1001:factory",
            question="Choose",
            choices=("approve SECRET-42", "reject"),
        )
    except GatewayHITLProjectionError as error:
        assert "sensitive" in str(error)
    else:
        raise AssertionError("sensitive HITL choice must fail closed")
